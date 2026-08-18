import os
import re
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

from ai_client import generate_test_case, analyze_bug_coverage
from excel_writer import append_test_case, find_similar_test_cases, get_tc_summaries_for_bug, COLUMNS
from bug_report_generator import (
    generate_bug_report_fields,
    format_bug_report,
    generate_bug_report_from_description,
    format_freeform_bug_report,
)
from yona_client import (
    fetch_issue,
    issue_to_bug_report_text,
    has_token,
    has_connection_settings,
    save_token,
    save_connection_settings,
    get_env_path,
)
from paths import get_desktop_path

DEFAULT_OUTPUT_FILE = str(get_desktop_path() / "testcase.xlsx")


def _sanitize_filename(text: str) -> str:

    text = re.sub(r'[\\/:*?"<>|]', "", text).strip()
    text = re.sub(r"\s+", "_", text)
    return text[:40] if text else "bugreport"


class TestCaseGeneratorApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("AI 기반 Test Case Generator")
        self.root.geometry("1000x900")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook.Tab", padding=[14, 8])
        style.map(
            "TNotebook.Tab",
            background=[("selected", "#2b6cb0"), ("!selected", "#d9d9d9")],
            foreground=[("selected", "white"), ("!selected", "#333333")],
        )

        self.current_tc_data = None  # 버그->TC 탭: 마지막 생성 시 bug_id 등 보관용
        self.current_bug_fields = None  # TC->버그 탭: 저장 파일명 생성용 (title 참조)
        self.current_yona_text = None  # Yona조회 탭: 조회된 버그 리포트 텍스트 (다른 탭으로 전달용)
        self.authored_report_fields = None  # 버그 작성 탭: 마지막으로 정리된 필드
        self.coverage_points = []  # 커버리지 탭: 분석된 검증 포인트 목록
        self.coverage_bug_report = ""  # 커버리지 탭: 커버리지 분석에 사용한 원본 버그 리포트
        self.coverage_missing_queue = []  # 커버리지 탭: 아직 생성 안 한 누락 포인트들
        self.coverage_current_point = None
        self.coverage_current_bug_id = "NA"
        self.output_path = tk.StringVar(value=DEFAULT_OUTPUT_FILE)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        tab_yona = ttk.Frame(self.notebook, padding=10)
        tab_author = ttk.Frame(self.notebook, padding=10)
        tab_forward = ttk.Frame(self.notebook, padding=10)
        tab_reverse = ttk.Frame(self.notebook, padding=10)
        tab_coverage = ttk.Frame(self.notebook, padding=10)

        self.TAB_YONA = 0
        self.TAB_AUTHOR = 1
        self.TAB_FORWARD = 2
        self.TAB_REVERSE = 3
        self.TAB_COVERAGE = 4

        self.notebook.add(tab_yona, text="Yona 조회")
        self.notebook.add(tab_author, text="버그 리포트 작성")
        self.notebook.add(tab_forward, text="버그 리포트 → 테스트케이스")
        self.notebook.add(tab_reverse, text="테스트케이스 → 버그 리포트")
        self.notebook.add(tab_coverage, text="커버리지 분석")

        self._build_yona_tab(tab_yona)
        self._build_author_tab(tab_author)
        self._build_forward_tab(tab_forward)
        self._build_reverse_tab(tab_reverse)
        self._build_coverage_tab(tab_coverage)

    # ==================================================================
    # 탭: 버그 리포트 작성 (자유 서술 -> 표준 양식)
    # ==================================================================
    def _build_author_tab(self, main):
        ttk.Label(
            main,
            text="버그를 편하게 서술하면, 아래 표준 양식(제목/버그설명/재현스텝/기대결과/실제결과/버전정보)으로 정리해드립니다.",
        ).pack(anchor="w", pady=(0, 8))

        self.author_input = tk.Text(main, height=15, wrap="word")
        self.author_input.pack(fill="both", expand=False, pady=(0, 8))

        action_frame = ttk.Frame(main)
        action_frame.pack(fill="x", pady=(0, 8))
        self.author_generate_btn = ttk.Button(
            action_frame, text="양식으로 정리", command=self._on_author_generate_clicked
        )
        self.author_generate_btn.pack(side="left")
        self.author_status = ttk.Label(action_frame, text="", foreground="#555555")
        self.author_status.pack(side="left", padx=12)

        ttk.Label(main, text="정리된 버그 리포트 (직접 수정 후 사용 가능)").pack(anchor="w")
        self.author_preview = tk.Text(main, height=11, wrap="word")
        self.author_preview.pack(fill="both", expand=True, pady=(2, 8))

        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill="x")
        self.author_save_btn = ttk.Button(
            btn_frame, text="텍스트 파일로 저장", command=self._on_author_save_clicked, state="disabled"
        )
        self.author_save_btn.pack(side="right", padx=(6, 0))
        self.author_send_btn = ttk.Button(
            btn_frame,
            text="테스트케이스 생성 탭으로 보내기 →",
            command=self._on_author_send_clicked,
            state="disabled",
        )
        self.author_send_btn.pack(side="right")

    def _on_author_generate_clicked(self):
        description = self.author_input.get("1.0", "end").strip()
        if not description:
            messagebox.showwarning("입력 필요", "버그 설명을 입력해주세요.")
            return

        self.author_generate_btn.config(state="disabled")
        self.author_save_btn.config(state="disabled")
        self.author_send_btn.config(state="disabled")
        self._set_status_author("로컬 AI 모델 호출 중...")
        self.author_preview.delete("1.0", "end")

        thread = threading.Thread(target=self._author_generate_worker, args=(description,), daemon=True)
        thread.start()

    def _author_generate_worker(self, description: str):
        try:
            fields = generate_bug_report_from_description(description)
        except RuntimeError as e:
            self.root.after(0, self._on_author_error, f"[설정 오류] {e}")
            return
        except ValueError as e:
            self.root.after(0, self._on_author_error, f"[AI 응답 오류] {e}")
            return
        except Exception as e:
            self.root.after(0, self._on_author_error, f"[예상치 못한 오류] {type(e).__name__}: {e}")
            return

        report = format_freeform_bug_report(fields)
        self.root.after(0, self._on_author_success, fields, report)

    def _on_author_success(self, fields: dict, report: str):
        self.authored_report_fields = fields
        self._set_status_author("정리 완료. 필요하면 직접 수정한 뒤 사용하세요.")
        self.author_preview.delete("1.0", "end")
        self.author_preview.insert("1.0", report)
        self.author_generate_btn.config(state="normal")
        self.author_save_btn.config(state="normal")
        self.author_send_btn.config(state="normal")

        if "(직접 입력 필요)" in report:
            messagebox.showinfo(
                "일부 항목 입력 필요",
                "실제 결과 또는 버전 정보가 서술에 없어서 비워뒀어요. "
                "미리보기에서 '(직접 입력 필요)' 부분을 채워주세요.",
            )

    def _on_author_error(self, message: str):
        self._set_status_author("정리 실패")
        self.author_preview.delete("1.0", "end")
        self.author_preview.insert("1.0", message)
        self.author_generate_btn.config(state="normal")
        messagebox.showerror("정리 실패", message)

    def _on_author_send_clicked(self):
        text = self.author_preview.get("1.0", "end").strip()
        if not text:
            return
        self.bug_input.delete("1.0", "end")
        self.bug_input.insert("1.0", text)
        self.notebook.select(self.TAB_FORWARD)
        self._set_status("버그 리포트 작성 탭에서 가져온 내용이 입력되었습니다. '테스트 케이스 생성'을 눌러주세요.")

    def _on_author_save_clicked(self):
        text = self.author_preview.get("1.0", "end").strip()
        if not text:
            return
        title_for_filename = self.authored_report_fields.get("title", "") if self.authored_report_fields else ""
        default_name = f"bugreport_{_sanitize_filename(title_for_filename)}.txt"
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("텍스트 파일", "*.txt")],
            initialfile=default_name,
            initialdir=str(get_desktop_path()),
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        except Exception as e:
            messagebox.showerror("저장 실패", f"{type(e).__name__}: {e}")
            return
        self._set_status_author(f"저장 완료: {path}")
        messagebox.showinfo("저장 완료", f"파일이 저장되었습니다:\n{path}")

    def _set_status_author(self, text: str):
        self.author_status.config(text=text)

    # ==================================================================
    # 탭 1: 버그 리포트 -> 테스트케이스
    # ==================================================================
    def _build_forward_tab(self, main):
        path_frame = ttk.Frame(main)
        path_frame.pack(fill="x", pady=(0, 8))
        ttk.Label(path_frame, text="저장 파일:").pack(side="left")
        ttk.Entry(path_frame, textvariable=self.output_path, width=50).pack(
            side="left", padx=6
        )
        ttk.Button(path_frame, text="찾아보기", command=self._browse_output_file).pack(
            side="left"
        )

        ttk.Label(main, text="Yona 버그 리포트 (제목, 버그 설명, 재현 스텝, 기대 결과 등 통째로 붙여넣기)").pack(
            anchor="w"
        )
        self.bug_input = tk.Text(main, height=22, wrap="word")
        self.bug_input.pack(fill="both", expand=False, pady=(2, 8))

        hint_frame = ttk.Frame(main)
        hint_frame.pack(fill="x", pady=(0, 8))
        ttk.Label(hint_frame, text="시나리오 힌트 (선택, 예: 공백만 입력하는 케이스만):").pack(
            side="left"
        )
        self.scenario_hint = tk.StringVar()
        ttk.Entry(hint_frame, textvariable=self.scenario_hint, width=45).pack(
            side="left", padx=6
        )

        action_frame = ttk.Frame(main)
        action_frame.pack(fill="x", pady=(0, 8))
        self.generate_btn = ttk.Button(
            action_frame, text="테스트 케이스 생성", command=self._on_generate_clicked
        )
        self.generate_btn.pack(side="left")
        self.status_label = ttk.Label(action_frame, text="", foreground="#555555")
        self.status_label.pack(side="left", padx=12)

        # ---- 생성 결과: 읽기전용 미리보기 대신, 필드별로 직접 수정 가능한 폼 ----
        form = ttk.LabelFrame(main, text="생성 결과 (직접 수정 후 저장 가능)")
        form.pack(fill="both", expand=True, pady=(4, 8))

        row1 = ttk.Frame(form)
        row1.pack(fill="x", padx=6, pady=(6, 4))
        ttk.Label(row1, text="카테고리:").pack(side="left")
        self.field_category = tk.StringVar()
        ttk.Entry(row1, textvariable=self.field_category, width=20).pack(side="left", padx=(4, 16))
        ttk.Label(row1, text="테스트 제목:").pack(side="left")
        self.field_title = tk.StringVar()
        ttk.Entry(row1, textvariable=self.field_title, width=45).pack(side="left", padx=4)

        self.field_purpose = self._add_field_row(form, "테스트 목적:", height=2)
        self.field_precondition = self._add_field_row(form, "사전 조건:", height=2)
        self.field_input_value = self._add_field_row(form, "입력값:", height=2)
        self.field_steps = self._add_field_row(form, "테스트 절차 (한 줄에 하나씩):", height=6)
        self.field_expected = self._add_field_row(form, "기대결과:", height=3)

        self.save_btn = ttk.Button(
            main, text="Excel에 저장", command=self._on_save_clicked, state="disabled"
        )
        self.save_btn.pack(anchor="e")

    def _add_field_row(self, parent, label_text, height):
        ttk.Label(parent, text=label_text).pack(anchor="w", padx=6)
        text_widget = tk.Text(parent, height=height, wrap="word")
        text_widget.pack(fill="x", padx=6, pady=(0, 6))
        return text_widget

    def _browse_output_file(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel 파일", "*.xlsx")],
            initialfile=self.output_path.get(),
        )
        if path:
            self.output_path.set(path)

    def _on_generate_clicked(self):
        bug_report = self.bug_input.get("1.0", "end").strip()
        if not bug_report:
            messagebox.showwarning("입력 필요", "버그 리포트를 붙여넣어 주세요.")
            return

        self.generate_btn.config(state="disabled")
        self.save_btn.config(state="disabled")
        self.current_tc_data = None
        self._set_status("로컬 AI 모델 호출 중...")
        self._clear_tc_form()

        thread = threading.Thread(
            target=self._generate_worker,
            args=(bug_report, self.scenario_hint.get().strip()),
            daemon=True,
        )
        thread.start()

    def _generate_worker(self, bug_report: str, scenario_hint: str):
        try:
            tc_data = generate_test_case(bug_report, scenario_hint=scenario_hint)
        except RuntimeError as e:
            self.root.after(0, self._on_generate_error, f"[설정 오류] {e}")
            return
        except ValueError as e:
            self.root.after(0, self._on_generate_error, f"[AI 응답 오류] {e}")
            return
        except Exception as e:
            self.root.after(0, self._on_generate_error, f"[예상치 못한 오류] {type(e).__name__}: {e}")
            return

        self.root.after(0, self._on_generate_success, tc_data)

    def _on_generate_success(self, tc_data: dict):
        self.current_tc_data = tc_data  # bug_id 보관용으로만 사용 (필드 값은 폼에서 읽음)
        self._set_status("생성 완료. 아래 내용을 직접 수정한 뒤 저장하세요.")
        self._fill_tc_form(tc_data)
        self.generate_btn.config(state="normal")
        self.save_btn.config(state="normal")
        self._warn_if_duplicate(tc_data)

    def _warn_if_duplicate(self, tc_data: dict):
        path = self.output_path.get().strip() or DEFAULT_OUTPUT_FILE
        try:
            matches = find_similar_test_cases(
                path, title=tc_data.get("title", ""), purpose=tc_data.get("purpose", "")
            )
        except Exception:
            return  # 중복 검사 자체가 실패해도 생성 흐름은 막지 않음
        if not matches:
            return
        lines = ["유사한 기존 테스트케이스가 있습니다 (중복일 수 있어요):\n"]
        for m in matches[:3]:
            pct = int(m["similarity"] * 100)
            lines.append(f"- {m['tc_id']} [{m['category']}]\n  {m['title']}\n  (유사도 {pct}%)")
        messagebox.showwarning("중복 가능성", "\n\n".join(lines))

    def _on_generate_error(self, message: str):
        self._set_status("생성 실패")
        self.generate_btn.config(state="normal")
        messagebox.showerror("생성 실패", message)

    def _on_save_clicked(self):
        if not self.current_tc_data:
            return
        tc_data = self._read_tc_form()
        tc_data["bug_id"] = self.current_tc_data.get("bug_id", "NA")

        path = self.output_path.get().strip() or DEFAULT_OUTPUT_FILE
        try:
            tc_id = append_test_case(path, tc_data["bug_id"], tc_data)
        except Exception as e:
            messagebox.showerror("저장 실패", f"{type(e).__name__}: {e}")
            return

        self._set_status(f"저장 완료: {tc_id} -> {path}")
        messagebox.showinfo("저장 완료", f"{tc_id} 가(이) {path}에 저장되었습니다.")

    def _clear_tc_form(self):
        self.field_category.set("")
        self.field_title.set("")
        for widget in (self.field_purpose, self.field_precondition,
                       self.field_input_value, self.field_steps, self.field_expected):
            widget.delete("1.0", "end")

    def _fill_tc_form(self, tc_data: dict):
        self._clear_tc_form()
        self.field_category.set(tc_data.get("category", ""))
        self.field_title.set(tc_data.get("title", ""))
        self.field_purpose.insert("1.0", tc_data.get("purpose", ""))
        self.field_precondition.insert("1.0", tc_data.get("precondition", ""))
        self.field_input_value.insert("1.0", tc_data.get("input_value", ""))
        self.field_steps.insert("1.0", "\n".join(tc_data.get("steps", [])))
        self.field_expected.insert("1.0", tc_data.get("expected", ""))

    def _read_tc_form(self) -> dict:
        steps_text = self.field_steps.get("1.0", "end").strip()
        steps = [line.strip() for line in steps_text.splitlines() if line.strip()]
        return {
            "category": self.field_category.get().strip(),
            "title": self.field_title.get().strip(),
            "purpose": self.field_purpose.get("1.0", "end").strip(),
            "precondition": self.field_precondition.get("1.0", "end").strip(),
            "input_value": self.field_input_value.get("1.0", "end").strip(),
            "steps": steps,
            "expected": self.field_expected.get("1.0", "end").strip(),
        }

    # ==================================================================
    # 탭 2: 테스트케이스 -> 버그 리포트
    # ==================================================================
    def _build_reverse_tab(self, main):
        ttk.Label(
            main, text="실패한 테스트케이스 (Excel 행 복사해서 그대로 붙여넣기 가능)"
        ).pack(anchor="w")
        self.tc_input = tk.Text(main, height=10, wrap="word")
        self.tc_input.pack(fill="both", expand=False, pady=(2, 8))

        ttk.Label(
            main, text="실제 결과 (테스트 시 실제로 어떻게 나왔는지, 필수)"
        ).pack(anchor="w")
        self.actual_result_input = tk.Text(main, height=3, wrap="word")
        self.actual_result_input.pack(fill="x", pady=(2, 8))

        version_frame = ttk.Frame(main)
        version_frame.pack(fill="x", pady=(0, 8))
        ttk.Label(version_frame, text="버전 정보 (예: v3.0.18.2, 필수):").pack(side="left")
        self.version_var = tk.StringVar()
        ttk.Entry(version_frame, textvariable=self.version_var, width=30).pack(
            side="left", padx=6
        )

        action_frame = ttk.Frame(main)
        action_frame.pack(fill="x", pady=(0, 8))
        self.reverse_generate_btn = ttk.Button(
            action_frame, text="버그 리포트 생성", command=self._on_reverse_generate_clicked
        )
        self.reverse_generate_btn.pack(side="left")
        self.reverse_status_label = ttk.Label(action_frame, text="", foreground="#555555")
        self.reverse_status_label.pack(side="left", padx=12)

        ttk.Label(main, text="생성된 버그 리포트 (직접 수정 후 저장 가능, Yona에 그대로 붙여넣기)").pack(anchor="w")
        self.reverse_preview = tk.Text(main, height=16, wrap="word")
        self.reverse_preview.pack(fill="both", expand=True, pady=(2, 8))

        self.reverse_save_btn = ttk.Button(
            main, text="텍스트 파일로 저장", command=self._on_reverse_save_clicked, state="disabled"
        )
        self.reverse_save_btn.pack(anchor="e")

    def _on_reverse_generate_clicked(self):
        tc_text = self.tc_input.get("1.0", "end").strip()
        actual_result = self.actual_result_input.get("1.0", "end").strip()
        version = self.version_var.get().strip()

        if not tc_text:
            messagebox.showwarning("입력 필요", "테스트케이스 내용을 붙여넣어 주세요.")
            return
        if not actual_result:
            messagebox.showwarning("입력 필요", "실제 결과는 AI가 알 수 없는 정보라 필수 입력입니다.")
            return
        if not version:
            messagebox.showwarning("입력 필요", "버전 정보를 입력해주세요.")
            return

        self.reverse_generate_btn.config(state="disabled")
        self.reverse_save_btn.config(state="disabled")
        self.current_bug_fields = None
        self._set_status_reverse("로컬 AI 모델 호출 중...")
        self.reverse_preview.delete("1.0", "end")

        thread = threading.Thread(
            target=self._reverse_worker,
            args=(tc_text, actual_result, version),
            daemon=True,
        )
        thread.start()

    def _reverse_worker(self, tc_text: str, actual_result: str, version: str):
        try:
            fields = generate_bug_report_fields(tc_text)
        except RuntimeError as e:
            self.root.after(0, self._on_reverse_error, f"[설정 오류] {e}")
            return
        except ValueError as e:
            self.root.after(0, self._on_reverse_error, f"[AI 응답 오류] {e}")
            return
        except Exception as e:
            self.root.after(0, self._on_reverse_error, f"[예상치 못한 오류] {type(e).__name__}: {e}")
            return

        report = format_bug_report(fields, actual_result, version)
        self.root.after(0, self._on_reverse_success, fields, report)

    def _on_reverse_success(self, fields: dict, report: str):
        self.current_bug_fields = fields
        self._set_status_reverse("생성 완료. 아래 내용을 직접 수정한 뒤 저장하세요.")
        self.reverse_preview.delete("1.0", "end")
        self.reverse_preview.insert("1.0", report)
        self.reverse_generate_btn.config(state="normal")
        self.reverse_save_btn.config(state="normal")

    def _on_reverse_error(self, message: str):
        self._set_status_reverse("생성 실패")
        self.reverse_preview.delete("1.0", "end")
        self.reverse_preview.insert("1.0", message)
        self.reverse_generate_btn.config(state="normal")
        messagebox.showerror("생성 실패", message)

    def _on_reverse_save_clicked(self):
        report_text = self.reverse_preview.get("1.0", "end").strip()
        if not report_text:
            return

        title_for_filename = self.current_bug_fields.get("title", "") if self.current_bug_fields else ""
        default_name = f"bugreport_{_sanitize_filename(title_for_filename)}.txt"
        default_dir = str(get_desktop_path())
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("텍스트 파일", "*.txt")],
            initialfile=default_name,
            initialdir=default_dir,
        )
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(report_text)
        except Exception as e:
            messagebox.showerror("저장 실패", f"{type(e).__name__}: {e}")
            return

        self._set_status_reverse(f"저장 완료: {path}")
        messagebox.showinfo("저장 완료", f"파일이 저장되었습니다:\n{path}")

    # ==================================================================
    # 탭 3: Yona 조회
    # ==================================================================
    def _build_yona_tab(self, main):
        settings_frame = ttk.Frame(main)
        settings_frame.pack(fill="x", pady=(0, 10))
        self.yona_settings_status = ttk.Label(settings_frame, text="", foreground="#555555")
        self.yona_settings_status.pack(side="left")
        ttk.Button(
            settings_frame, text="접속 설정", command=self._on_set_connection_clicked
        ).pack(side="left", padx=(10, 4))
        ttk.Button(
            settings_frame, text="토큰 설정", command=self._on_set_token_clicked
        ).pack(side="left")
        self._refresh_yona_status()

        ttk.Label(
            main, text="버그 번호만 입력하면 Yona에서 자동으로 가져옵니다"
        ).pack(anchor="w", pady=(0, 8))

        input_frame = ttk.Frame(main)
        input_frame.pack(fill="x", pady=(0, 8))
        ttk.Label(input_frame, text="버그 번호:").pack(side="left")
        self.yona_issue_number = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.yona_issue_number, width=15).pack(
            side="left", padx=6
        )
        self.yona_fetch_btn = ttk.Button(
            input_frame, text="조회", command=self._on_yona_fetch_clicked
        )
        self.yona_fetch_btn.pack(side="left")
        self.yona_status_label = ttk.Label(input_frame, text="", foreground="#555555")
        self.yona_status_label.pack(side="left", padx=12)

        ttk.Label(main, text="조회 결과 미리보기").pack(anchor="w")
        self.yona_preview = tk.Text(main, height=18, wrap="word", state="disabled", bg="#f7f7f7")
        self.yona_preview.pack(fill="both", expand=True, pady=(2, 8))

        send_frame = ttk.Frame(main)
        send_frame.pack(fill="x")
        self.yona_send_btn = ttk.Button(
            send_frame,
            text="테스트케이스 생성 탭으로 보내기 →",
            command=self._on_yona_send_clicked,
            state="disabled",
        )
        self.yona_send_btn.pack(side="right", padx=(6, 0))
        self.yona_send_coverage_btn = ttk.Button(
            send_frame,
            text="커버리지 분석 탭으로 보내기 →",
            command=self._on_yona_send_to_coverage_clicked,
            state="disabled",
        )
        self.yona_send_coverage_btn.pack(side="right")

    def _refresh_yona_status(self):
        if has_connection_settings():
            self.yona_settings_status.config(text="설정 완료 ✓ (접속정보 + 토큰)", foreground="#2e7d32")
        elif has_token():
            self.yona_settings_status.config(text="토큰은 있음 — 접속 설정(도메인/프로젝트)이 필요해요", foreground="#c62828")
        else:
            self.yona_settings_status.config(text="접속 설정 + 토큰이 필요해요", foreground="#c62828")

    def _on_set_connection_clicked(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Yona 접속 설정")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="회사/조직마다 다른 값이라, 이 PC에만 저장됩니다.").grid(
            row=0, column=0, columnspan=2, padx=10, pady=(10, 6), sticky="w"
        )

        ttk.Label(dialog, text="Yona 주소 (예: https://yona.example.com):").grid(
            row=1, column=0, padx=10, pady=4, sticky="w"
        )
        base_url_var = tk.StringVar(value=os.getenv("YONA_BASE_URL", ""))
        ttk.Entry(dialog, textvariable=base_url_var, width=40).grid(row=1, column=1, padx=10, pady=4)

        ttk.Label(dialog, text="Owner (팀/조직 이름):").grid(row=2, column=0, padx=10, pady=4, sticky="w")
        owner_var = tk.StringVar(value=os.getenv("YONA_OWNER", ""))
        ttk.Entry(dialog, textvariable=owner_var, width=40).grid(row=2, column=1, padx=10, pady=4)

        ttk.Label(dialog, text="Project (프로젝트 이름):").grid(row=3, column=0, padx=10, pady=4, sticky="w")
        project_var = tk.StringVar(value=os.getenv("YONA_PROJECT", ""))
        ttk.Entry(dialog, textvariable=project_var, width=40).grid(row=3, column=1, padx=10, pady=4)

        def on_save():
            try:
                save_connection_settings(base_url_var.get(), owner_var.get(), project_var.get())
            except Exception as e:
                messagebox.showerror("저장 실패", f"{type(e).__name__}: {e}", parent=dialog)
                return
            self._refresh_yona_status()
            dialog.destroy()
            messagebox.showinfo("저장 완료", "접속 설정이 저장되었습니다. (재빌드해도 유지됩니다)")

        btn_frame = ttk.Frame(dialog)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=(6, 10))
        ttk.Button(btn_frame, text="저장", command=on_save).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="취소", command=dialog.destroy).pack(side="left", padx=4)

    def _on_set_token_clicked(self):
        token = simpledialog.askstring(
            "Yona API Token 설정",
            "Yona 계정 설정 > API Token 에서 발급받은 값을 입력하세요:\n"
            f"(저장 위치: {get_env_path()})",
            show="*",
            parent=self.root,
        )
        if not token:
            return
        try:
            save_token(token)
        except Exception as e:
            messagebox.showerror("저장 실패", f"{type(e).__name__}: {e}")
            return
        self._refresh_yona_status()
        messagebox.showinfo("저장 완료", "토큰이 저장되었습니다. 이제 재빌드해도 유지됩니다.")

    def _on_yona_fetch_clicked(self):
        issue_number = self.yona_issue_number.get().strip()
        if not issue_number.isdigit():
            messagebox.showwarning("입력 필요", "버그 번호는 숫자만 입력해주세요.")
            return

        self.yona_fetch_btn.config(state="disabled")
        self.yona_send_btn.config(state="disabled")
        self.yona_send_coverage_btn.config(state="disabled")
        self._set_status_yona("Yona에서 조회 중...")
        self._yona_set_preview("")

        thread = threading.Thread(
            target=self._yona_fetch_worker, args=(issue_number,), daemon=True
        )
        thread.start()

    def _yona_fetch_worker(self, issue_number: str):
        try:
            issue = fetch_issue(issue_number)
        except RuntimeError as e:
            self.root.after(0, self._on_yona_fetch_error, f"[조회 실패] {e}")
            return
        except Exception as e:
            self.root.after(0, self._on_yona_fetch_error, f"[예상치 못한 오류] {type(e).__name__}: {e}")
            return

        bug_report_text = issue_to_bug_report_text(issue)
        self.root.after(0, self._on_yona_fetch_success, issue, bug_report_text)

    def _on_yona_fetch_success(self, issue: dict, bug_report_text: str):
        self.current_yona_text = bug_report_text
        self._set_status_yona(f"조회 완료: [{issue.get('number')}] {issue.get('title')}")
        self._yona_set_preview(bug_report_text)
        self.yona_fetch_btn.config(state="normal")
        self.yona_send_btn.config(state="normal")
        self.yona_send_coverage_btn.config(state="normal")

    def _on_yona_fetch_error(self, message: str):
        self._set_status_yona("조회 실패")
        self._yona_set_preview(message)
        self.yona_fetch_btn.config(state="normal")
        messagebox.showerror("조회 실패", message)

    def _on_yona_send_clicked(self):
        text = getattr(self, "current_yona_text", None)
        if not text:
            return
        self.bug_input.delete("1.0", "end")
        self.bug_input.insert("1.0", text)
        self.notebook.select(self.TAB_FORWARD)
        self._set_status("Yona에서 가져온 내용이 입력되었습니다. '테스트 케이스 생성'을 눌러주세요.")

    def _on_yona_send_to_coverage_clicked(self):
        text = getattr(self, "current_yona_text", None)
        if not text:
            return
        self.receive_bug_report_for_coverage(text)
        self.notebook.select(self.TAB_COVERAGE)

    def _set_status_yona(self, text: str):
        self.yona_status_label.config(text=text)

    def _yona_set_preview(self, text: str):
        self.yona_preview.config(state="normal")
        self.yona_preview.delete("1.0", "end")
        self.yona_preview.insert("1.0", text)
        self.yona_preview.config(state="disabled")

    # ==================================================================
    # 공용 표시 헬퍼
    # ==================================================================
    def _set_status(self, text: str):
        self.status_label.config(text=text)

    def _set_status_reverse(self, text: str):
        self.reverse_status_label.config(text=text)

    # ==================================================================
    # 탭 4: 커버리지 분석
    # ==================================================================
    def _build_coverage_tab(self, main):
        ttk.Label(
            main,
            text="버그 리포트에 실제로 적힌 검증 포인트를 뽑아서, 이미 작성된 TC가 그걸 빠짐없이 반영했는지 대조합니다.",
        ).pack(anchor="w", pady=(0, 8))

        # 버그 리포트 입력창: 창을 늘리면 같이 커지도록 expand=True
        self.coverage_input = tk.Text(main, height=16, wrap="word")
        self.coverage_input.pack(fill="both", expand=True, pady=(0, 8))

        action_frame = ttk.Frame(main)
        action_frame.pack(fill="x", pady=(0, 8))
        self.coverage_analyze_btn = ttk.Button(
            action_frame, text="커버리지 분석", command=self._on_coverage_analyze_clicked
        )
        self.coverage_analyze_btn.pack(side="left")
        self.coverage_status = ttk.Label(action_frame, text="", foreground="#555555")
        self.coverage_status.pack(side="left", padx=12)

        ttk.Label(main, text="버그 검증 포인트").pack(anchor="w")
        checklist_container = ttk.Frame(main, relief="groove", borderwidth=1)
        checklist_container.pack(fill="both", expand=True, pady=(2, 8))
        self.coverage_checklist_frame = ttk.Frame(checklist_container)
        self.coverage_checklist_frame.pack(fill="both", expand=True, padx=8, pady=8, anchor="nw")

        queue_frame = ttk.Frame(main)
        queue_frame.pack(fill="x", pady=(0, 4))
        self.coverage_gen_btn = ttk.Button(
            queue_frame, text="다음 누락 항목 생성 →", command=self._on_coverage_gen_next_clicked,
            state="disabled",
        )
        self.coverage_gen_btn.pack(side="left")
        self.coverage_progress_label = ttk.Label(queue_frame, text="", foreground="#555555")
        self.coverage_progress_label.pack(side="left", padx=12)


        nav_frame = ttk.Frame(main)
        nav_frame.pack(fill="x", pady=(0, 6))
        self.coverage_prev_btn = ttk.Button(
            nav_frame, text="◀ 이전 항목", command=self._on_coverage_prev_clicked, state="disabled"
        )
        self.coverage_prev_btn.pack(side="left")
        self.coverage_next_history_btn = ttk.Button(
            nav_frame, text="다음 항목 ▶", command=self._on_coverage_next_history_clicked, state="disabled"
        )
        self.coverage_next_history_btn.pack(side="left", padx=(6, 0))
        self.coverage_history_label = ttk.Label(nav_frame, text="", foreground="#555555")
        self.coverage_history_label.pack(side="left", padx=12)


        form = ttk.LabelFrame(main, text="생성된 테스트케이스 (직접 수정 후 저장 가능)")
        form.pack(fill="x", expand=False, pady=(4, 8))

        row1 = ttk.Frame(form)
        row1.pack(fill="x", padx=6, pady=(6, 4))
        ttk.Label(row1, text="카테고리:").pack(side="left")
        self.cov_field_category = tk.StringVar()
        ttk.Entry(row1, textvariable=self.cov_field_category, width=20).pack(side="left", padx=(4, 16))
        ttk.Label(row1, text="테스트 제목:").pack(side="left")
        self.cov_field_title = tk.StringVar()
        ttk.Entry(row1, textvariable=self.cov_field_title, width=40).pack(side="left", padx=4)

        self.cov_field_purpose = self._add_field_row(form, "테스트 목적:", height=2)
        self.cov_field_precondition = self._add_field_row(form, "사전 조건:", height=2)
        self.cov_field_input_value = self._add_field_row(form, "입력값:", height=2)
        self.cov_field_steps = self._add_field_row(form, "테스트 절차 (한 줄에 하나씩):", height=6)
        self.cov_field_expected = self._add_field_row(form, "기대결과:", height=2)

        self.coverage_save_btn = ttk.Button(
            main, text="이 항목 저장", command=self._on_coverage_save_clicked, state="disabled"
        )
        self.coverage_save_btn.pack(anchor="e")


        self.coverage_history = []  # [{"point": str, "tc_data": dict}, ...]
        self.coverage_history_index = -1

    def _on_coverage_analyze_clicked(self):
        bug_report = self.coverage_input.get("1.0", "end").strip()
        if not bug_report:
            messagebox.showwarning("입력 필요", "버그 리포트를 붙여넣어 주세요.")
            return

        self.coverage_bug_report = bug_report
        self.coverage_analyze_btn.config(state="disabled")
        self.coverage_gen_btn.config(state="disabled")
        self.coverage_save_btn.config(state="disabled")
        self.coverage_missing_queue = []
        self.coverage_history = []
        self.coverage_history_index = -1
        self._refresh_coverage_nav()
        self._set_status_coverage("기존 TC 확인 및 검증 포인트 분석 중...")
        self._clear_coverage_checklist()
        self._clear_coverage_form()

        thread = threading.Thread(target=self._coverage_analyze_worker, args=(bug_report,), daemon=True)
        thread.start()

    def _coverage_analyze_worker(self, bug_report: str):
        bug_id_match = re.search(r"\b(\d{2,6})\b", bug_report)
        bug_id = bug_id_match.group(1) if bug_id_match else "NA"

        path = self.output_path.get().strip() or DEFAULT_OUTPUT_FILE
        try:
            existing_summaries = get_tc_summaries_for_bug(path, bug_id) if bug_id != "NA" else []
        except Exception:
            existing_summaries = []

        try:
            points = analyze_bug_coverage(bug_report, existing_tc_summaries=existing_summaries)
        except RuntimeError as e:
            self.root.after(0, self._on_coverage_analyze_error, f"[설정 오류] {e}")
            return
        except ValueError as e:
            self.root.after(0, self._on_coverage_analyze_error, f"[AI 응답 오류] {e}")
            return
        except Exception as e:
            self.root.after(0, self._on_coverage_analyze_error, f"[예상치 못한 오류] {type(e).__name__}: {e}")
            return

        self.root.after(0, self._on_coverage_analyze_success, points, bug_id, len(existing_summaries))

    def _on_coverage_analyze_success(self, points: list, bug_id: str, existing_count: int):
        self.coverage_points = points
        missing = [p for p in points if not p.get("covered")]
        if bug_id == "NA":
            self._set_status_coverage(f"버그 번호를 못 찾음 - 기존 TC 비교 없이 분석함 (총 {len(points)}건)")
        else:
            self._set_status_coverage(
                f"버그 #{bug_id} 기존 TC {existing_count}개와 대조 완료 - 누락 {len(missing)}건 발견"
            )
        self._render_coverage_checklist(points)
        self.coverage_analyze_btn.config(state="normal")

        self.coverage_missing_queue = list(missing)
        self.coverage_gen_btn.config(
            state="normal" if self.coverage_missing_queue else "disabled",
            text="다음 누락 항목 생성 →" if self.coverage_missing_queue else "누락된 항목 없음",
        )

    def _on_coverage_analyze_error(self, message: str):
        self._set_status_coverage("분석 실패")
        self.coverage_analyze_btn.config(state="normal")
        messagebox.showerror("분석 실패", message)

    def _clear_coverage_checklist(self):
        for widget in self.coverage_checklist_frame.winfo_children():
            widget.destroy()

    def _render_coverage_checklist(self, points: list):
        self._clear_coverage_checklist()
        for p in points:
            mark = "☑" if p.get("covered") else "☐"
            color = "#2e7d32" if p.get("covered") else "#c62828"
            label = ttk.Label(self.coverage_checklist_frame, text=f"{mark}  {p.get('point')}", foreground=color)
            label.pack(anchor="w", pady=2)

    def _on_coverage_gen_next_clicked(self):
        if not self.coverage_missing_queue:
            messagebox.showinfo("완료", "생성할 누락 항목이 더 없습니다.")
            return

        point = self.coverage_missing_queue.pop(0)
        self.coverage_current_point = point.get("point")
        remaining = len(self.coverage_missing_queue)
        self._set_status_coverage(f"'{self.coverage_current_point}' 생성 중...")
        self.coverage_progress_label.config(text=f"(남은 누락 항목 {remaining}개)")
        self.coverage_gen_btn.config(state="disabled")
        self.coverage_save_btn.config(state="disabled")
        self._clear_coverage_form()

        thread = threading.Thread(
            target=self._coverage_gen_worker, args=(self.coverage_current_point,), daemon=True
        )
        thread.start()

    def _coverage_gen_worker(self, scenario: str):
        try:
            tc_data = generate_test_case(self.coverage_bug_report, scenario_hint=scenario)
        except RuntimeError as e:
            self.root.after(0, self._on_coverage_gen_error, f"[설정 오류] {e}")
            return
        except ValueError as e:
            self.root.after(0, self._on_coverage_gen_error, f"[AI 응답 오류] {e}")
            return
        except Exception as e:
            self.root.after(0, self._on_coverage_gen_error, f"[예상치 못한 오류] {type(e).__name__}: {e}")
            return

        self.root.after(0, self._on_coverage_gen_success, scenario, tc_data)

    def _on_coverage_gen_success(self, scenario: str, tc_data: dict):
        self.coverage_current_bug_id = tc_data.get("bug_id", "NA")
        self._fill_cov_form(tc_data)
        self._set_status_coverage(f"'{scenario}' 생성 완료. 확인 후 저장하세요.")
        self.coverage_gen_btn.config(
            state="normal" if self.coverage_missing_queue else "disabled",
            text="다음 누락 항목 생성 →" if self.coverage_missing_queue else "모든 항목 처리 완료",
        )
        self.coverage_save_btn.config(state="normal")


        self.coverage_history.append({"point": scenario, "tc_data": dict(tc_data)})
        self.coverage_history_index = len(self.coverage_history) - 1
        self._refresh_coverage_nav()

        path = self.output_path.get().strip() or DEFAULT_OUTPUT_FILE
        try:
            matches = find_similar_test_cases(
                path, title=tc_data.get("title", ""), purpose=tc_data.get("purpose", "")
            )
        except Exception:
            matches = []
        if matches:
            top = matches[0]
            pct = int(top["similarity"] * 100)
            messagebox.showwarning("중복 가능성", f"기존 저장된 '{top['tc_id']}'와 유사합니다 (유사도 {pct}%).")

    def _on_coverage_gen_error(self, message: str):
        self._set_status_coverage("생성 실패")
        self.coverage_gen_btn.config(state="normal" if self.coverage_missing_queue else "disabled")
        messagebox.showerror("생성 실패", message)

    def _on_coverage_save_clicked(self):
        tc_data = self._read_cov_form()
        tc_data["bug_id"] = self.coverage_current_bug_id


        if 0 <= self.coverage_history_index < len(self.coverage_history):
            self.coverage_history[self.coverage_history_index]["tc_data"] = dict(tc_data)

        path = self.output_path.get().strip() or DEFAULT_OUTPUT_FILE
        try:
            tc_id = append_test_case(path, tc_data["bug_id"], tc_data)
        except Exception as e:
            messagebox.showerror("저장 실패", f"{type(e).__name__}: {e}")
            return
        self._set_status_coverage(f"저장 완료: {tc_id} -> {path}")
        messagebox.showinfo("저장 완료", f"{tc_id} 가(이) 저장되었습니다.")

    def _on_coverage_prev_clicked(self):
        if self.coverage_history_index <= 0:
            return
        self._save_current_form_to_history()
        self.coverage_history_index -= 1
        self._load_history_item(self.coverage_history_index)

    def _on_coverage_next_history_clicked(self):
        if self.coverage_history_index >= len(self.coverage_history) - 1:
            return
        self._save_current_form_to_history()
        self.coverage_history_index += 1
        self._load_history_item(self.coverage_history_index)

    def _save_current_form_to_history(self):

        if 0 <= self.coverage_history_index < len(self.coverage_history):
            tc_data = self._read_cov_form()
            self.coverage_history[self.coverage_history_index]["tc_data"] = tc_data

    def _load_history_item(self, index: int):
        item = self.coverage_history[index]
        self.coverage_current_bug_id = item["tc_data"].get("bug_id", "NA")
        self._fill_cov_form(item["tc_data"])
        self.coverage_save_btn.config(state="normal")
        self._set_status_coverage(f"'{item['point']}' 항목을 보고 있습니다. (수정 후 다시 저장 가능)")
        self._refresh_coverage_nav()

    def _refresh_coverage_nav(self):
        total = len(self.coverage_history)
        idx = self.coverage_history_index
        if total == 0:
            self.coverage_history_label.config(text="")
            self.coverage_prev_btn.config(state="disabled")
            self.coverage_next_history_btn.config(state="disabled")
            return

        self.coverage_history_label.config(text=f"{idx + 1} / {total}  -  {self.coverage_history[idx]['point']}")
        self.coverage_prev_btn.config(state="normal" if idx > 0 else "disabled")
        self.coverage_next_history_btn.config(state="normal" if idx < total - 1 else "disabled")

    def _clear_coverage_form(self):
        self.cov_field_category.set("")
        self.cov_field_title.set("")
        for widget in (self.cov_field_purpose, self.cov_field_precondition,
                       self.cov_field_input_value, self.cov_field_steps, self.cov_field_expected):
            widget.delete("1.0", "end")

    def _fill_cov_form(self, tc_data: dict):
        self._clear_coverage_form()
        self.cov_field_category.set(tc_data.get("category", ""))
        self.cov_field_title.set(tc_data.get("title", ""))
        self.cov_field_purpose.insert("1.0", tc_data.get("purpose", ""))
        self.cov_field_precondition.insert("1.0", tc_data.get("precondition", ""))
        self.cov_field_input_value.insert("1.0", tc_data.get("input_value", ""))
        self.cov_field_steps.insert("1.0", "\n".join(tc_data.get("steps", [])))
        self.cov_field_expected.insert("1.0", tc_data.get("expected", ""))

    def _read_cov_form(self) -> dict:
        steps_text = self.cov_field_steps.get("1.0", "end").strip()
        steps = [line.strip() for line in steps_text.splitlines() if line.strip()]
        return {
            "category": self.cov_field_category.get().strip(),
            "title": self.cov_field_title.get().strip(),
            "purpose": self.cov_field_purpose.get("1.0", "end").strip(),
            "precondition": self.cov_field_precondition.get("1.0", "end").strip(),
            "input_value": self.cov_field_input_value.get("1.0", "end").strip(),
            "steps": steps,
            "expected": self.cov_field_expected.get("1.0", "end").strip(),
        }

    def _set_status_coverage(self, text: str):
        self.coverage_status.config(text=text)

    def receive_bug_report_for_coverage(self, text: str):

        self.coverage_input.delete("1.0", "end")
        self.coverage_input.insert("1.0", text)
        self._clear_coverage_checklist()
        self._clear_coverage_form()
        self.coverage_missing_queue = []
        self.coverage_history = []
        self.coverage_history_index = -1
        self._refresh_coverage_nav()
        self.coverage_gen_btn.config(state="disabled")
        self.coverage_save_btn.config(state="disabled")
        self._set_status_coverage("Yona에서 가져온 내용이 입력되었습니다. '커버리지 분석'을 눌러주세요.")


def main():
    root = tk.Tk()
    app = TestCaseGeneratorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
