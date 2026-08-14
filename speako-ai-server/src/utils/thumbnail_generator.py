"""슬라이드 썸네일 생성 — PPTX/PDF를 슬라이드별 PNG로 만든다.

편집 화면 왼쪽의 슬라이드 미리보기 목록(파워포인트 좌측 패널 같은 화면)에 쓴다.
브라우저에서 PPTX를 그릴 방법이 없어서 서버가 만들어 줘야 한다.

## 변환 경로

    PPTX ──(LibreOffice headless)──> PDF ──(pdftoppm)──> 슬라이드별 PNG

PDF를 거치는 이유: LibreOffice의 PPTX→PNG 직접 변환은 첫 장만 내보낸다. PDF로 한 번
바꾸면 페이지 수 = 슬라이드 수가 되어 pdftoppm이 장별로 잘라준다. 업로드가 PDF면 앞
단계를 건너뛴다.

## 메모리를 왜 이렇게 조심하나

배포된 EC2가 t3.small(2GB)이고 스프링·MySQL·AI 서버가 같이 산다. LibreOffice는 변환 중
200~400MB를 잡기 때문에, 두 개가 동시에 돌면 다른 프로세스가 OOM으로 죽는다. 그래서
**전역 락으로 한 번에 하나만** 돌리고, 타임아웃을 걸어 매달린 프로세스를 끊는다.

LibreOffice나 pdftoppm이 없는 환경(로컬 개발용 윈도우 등)에서는 조용히 'unavailable'을
돌려준다. 썸네일이 없다고 업로드가 실패하면 안 된다.
"""
import glob
import os
import re
import shutil
import subprocess
import tempfile
import threading

from db.database import DATA_DIR

THUMBNAIL_DIR = os.path.join(DATA_DIR, "thumbnails")

# 미리보기 카드 하나가 화면에서 200px 안팎이라 480px면 2배 해상도로 충분하다.
# 더 키우면 변환 시간과 저장 용량만 늘고 눈에 띄는 차이가 없다.
THUMBNAIL_WIDTH_PX = 480

# 변환이 이 시간을 넘기면 끊는다. 27장짜리 실측이 수십 초 수준이라 넉넉히 잡은 값이다.
# 매달린 LibreOffice를 방치하면 메모리를 잡은 채 남는다.
CONVERT_TIMEOUT_SECONDS = 180

# 슬라이드가 아주 많은 파일에서 디스크와 시간이 폭주하지 않게 상한을 둔다.
# (업로드 자체 상한은 main.MAX_SLIDES_PER_PROJECT이고, 여기는 썸네일만의 상한이다)
MAX_THUMBNAIL_SLIDES = 60

# LibreOffice 두 개가 동시에 돌면 메모리가 터진다. 프로세스 전역으로 하나만 통과시킨다.
_convert_lock = threading.Lock()

_PAGE_SUFFIX = re.compile(r"-(\d+)\.png$")


def is_available():
    """변환 도구가 설치돼 있는지. 없으면 썸네일 기능만 조용히 꺼진다."""
    return bool(_soffice_path()) and bool(shutil.which("pdftoppm"))


def _soffice_path():
    # 데비안 계열은 soffice, 일부 이미지는 libreoffice로만 잡힌다.
    return shutil.which("soffice") or shutil.which("libreoffice")


def project_dir(project_id):
    return os.path.join(THUMBNAIL_DIR, str(int(project_id)))


def thumbnail_path(project_id, slide_number):
    """있으면 파일 경로, 없으면 None."""
    path = os.path.join(project_dir(project_id), f"{int(slide_number)}.png")
    return path if os.path.exists(path) else None


def available_slide_numbers(project_id):
    directory = project_dir(project_id)
    if not os.path.isdir(directory):
        return []
    numbers = []
    for name in os.listdir(directory):
        stem, ext = os.path.splitext(name)
        if ext == ".png" and stem.isdigit():
            numbers.append(int(stem))
    return sorted(numbers)


def clear_project(project_id):
    """프로젝트 삭제 시 썸네일도 같이 지운다(안 지우면 디스크에 계속 쌓인다)."""
    shutil.rmtree(project_dir(project_id), ignore_errors=True)


def _run(command, cwd=None):
    """실패해도 예외를 올리지 않고 (성공여부, 메시지)를 돌려준다."""
    try:
        completed = subprocess.run(
            command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=CONVERT_TIMEOUT_SECONDS, check=False,
        )
    except subprocess.TimeoutExpired:
        return False, f"시간 초과({CONVERT_TIMEOUT_SECONDS}초)"
    except OSError as err:
        return False, f"실행 실패: {err}"

    if completed.returncode != 0:
        tail = (completed.stdout or b"").decode("utf-8", "replace")[-300:]
        return False, f"종료코드 {completed.returncode} {tail}"
    return True, ""


def _to_pdf(source_path, work_dir):
    """PPTX를 PDF로 바꾼다. 이미 PDF면 그대로 쓴다."""
    if os.path.splitext(source_path)[1].lower() == ".pdf":
        return source_path, ""

    soffice = _soffice_path()
    if not soffice:
        return None, "LibreOffice가 설치돼 있지 않습니다."

    # 프로필 경로를 요청마다 따로 준다. 공용 프로필을 쓰면 이전 실행이 남긴 잠금 파일 때문에
    # "이미 실행 중"으로 판단하고 조용히 아무것도 안 만든 채 성공으로 끝나는 일이 있다.
    profile_dir = os.path.join(work_dir, "lo_profile")
    ok, message = _run([
        soffice,
        f"-env:UserInstallation=file://{profile_dir}",
        "--headless", "--norestore", "--nolockcheck", "--nodefault",
        "--convert-to", "pdf", "--outdir", work_dir, source_path,
    ], cwd=work_dir)
    if not ok:
        return None, f"PDF 변환 실패: {message}"

    produced = glob.glob(os.path.join(work_dir, "*.pdf"))
    if not produced:
        return None, "PDF 변환 결과가 없습니다."
    return produced[0], ""


def _to_pngs(pdf_path, work_dir):
    """PDF를 페이지별 PNG로 자른다. 파일명은 page-1.png, page-2.png ..."""
    prefix = os.path.join(work_dir, "page")
    ok, message = _run([
        "pdftoppm", "-png",
        "-scale-to-x", str(THUMBNAIL_WIDTH_PX), "-scale-to-y", "-1",
        "-l", str(MAX_THUMBNAIL_SLIDES),  # 앞에서부터 이 장수까지만
        pdf_path, prefix,
    ])
    if not ok:
        return [], f"PNG 변환 실패: {message}"

    pages = []
    for path in glob.glob(prefix + "-*.png"):
        matched = _PAGE_SUFFIX.search(os.path.basename(path))
        if matched:
            pages.append((int(matched.group(1)), path))
    pages.sort()
    return pages, ""


def generate_for_project(project_id, source_path):
    """업로드된 파일에서 썸네일을 만들어 data/thumbnails/{project_id}/{n}.png로 저장한다.

    반환: {"status": "ready" | "failed" | "unavailable", "count": int, "message": str}
    예외를 올리지 않는다 — 썸네일 실패가 업로드나 대본 생성을 막으면 안 된다.
    """
    if not is_available():
        return {"status": "unavailable", "count": 0,
                "message": "변환 도구(LibreOffice/pdftoppm)가 없어 썸네일을 건너뜁니다."}

    if not source_path or not os.path.exists(source_path):
        return {"status": "failed", "count": 0, "message": "원본 파일을 찾을 수 없습니다."}

    destination = project_dir(project_id)
    work_dir = tempfile.mkdtemp(prefix="thumb_")
    try:
        # LibreOffice 동시 실행 금지. 대기 시간이 길어져도 죽는 것보다 낫다.
        with _convert_lock:
            pdf_path, message = _to_pdf(source_path, work_dir)
            if not pdf_path:
                return {"status": "failed", "count": 0, "message": message}

            pages, message = _to_pngs(pdf_path, work_dir)
            if not pages:
                return {"status": "failed", "count": 0, "message": message or "생성된 페이지가 없습니다."}

        # 다 만든 뒤에 한꺼번에 옮긴다. 만드는 도중에 조회가 들어와도 반쪽짜리 목록이 안 보인다.
        os.makedirs(destination, exist_ok=True)
        for page_number, path in pages:
            shutil.move(path, os.path.join(destination, f"{page_number}.png"))

        return {"status": "ready", "count": len(pages), "message": ""}
    except Exception as err:  # 여기서 터져도 업로드는 성공한 상태여야 한다
        return {"status": "failed", "count": 0, "message": f"예기치 못한 오류: {err}"}
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
