import bug_report_generator as brg

BASE = {
    "title": "공백 입력이 저장됨",
    "description": "공백만 입력해도 저장된다.",
    "location": "도메인 관리",
    "repro_steps": ["화면 진입", "공백 입력"],
    "expected": "저장이 차단되어야 함",
}


def test_freeform_format_handles_none_actual():
    # 의심 결함: 모델이 null을 돌려주면 None.strip()으로 AttributeError (실패 예상)
    fields = {**BASE, "actual": None, "version": "v1.0"}
    report = brg.format_freeform_bug_report(fields)
    assert "4.실제 결과\n(직접 입력 필요)" in report


def test_freeform_format_handles_none_version():
    # 의심 결함: version이 None인 경우도 동일 (실패 예상)
    fields = {**BASE, "actual": "저장됨", "version": None}
    report = brg.format_freeform_bug_report(fields)
    assert "5.버전 정보\n(직접 입력 필요)" in report