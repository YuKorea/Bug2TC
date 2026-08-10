"""
gui.py
AI 기반 Test Case Generator - Tkinter GUI (V2, 양방향 지원)

탭 1: 버그 리포트 -> 테스트케이스 (Excel 저장)
탭 2: 테스트케이스 -> 버그 리포트 (텍스트 파일 저장)

main.py(CLI)와 동일한 로직(ai_client, excel_writer, bug_report_generator)을
그대로 재사용합니다. API 호출은 백그라운드 스레드에서 실행해서 UI가 멈추지 않도록 처리했습니다.

실행: python gui.py
"""

import re
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from ai_client import generate_test_case
from excel_writer import append_test_case, find_similar_test_cases, COLUMNS
from bug_report_generator import generate_bug_report_fields, format_bug_report
from paths import get_desktop_path

DEFAULT_OUTPUT_FILE = str(get_desktop_path() / "testcase.xlsx")


def _sanitize_filename(text: str) -> str:
    """파일명으로 못 쓰는 문자 제거/치환, 너무 길면 자름."""
    text = re.sub(r'[\\/:*?"<>|]', "", text).strip()
    text = re.sub(r"\s+", "_", text)
    return text[:40] if text else "bugreport"


class TestCaseGeneratorApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("AI 기반 Test Case Generator")
        self.root.geometry("900x780")

        self.current_tc_data = None  # 탭1: 마지막으로 생성된 테스트케이스
        self.current_bug_fields = None  # 탭2: 마지막으로 생성된 버그리포트 필드
        self.current_bug_report_text = None  # 탭2: 최종 조립된 버그리포트 텍스트
        self.output_path = tk.StringVar(value=DEFAULT_OUTPUT_FILE)

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        tab1 = ttk.Frame(notebook, padding=10)
        tab2 = ttk.Frame(notebook, padding=10)
        notebook.add(tab1, text="버그 리포트 → 테스트케이스")
        notebook.add(tab2, text="테스트케이스 → 버그 리포트")

        self._build_forward_tab(tab1)
        self._build_reverse_tab(tab2)

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
        self.bug_input = tk.Text(main, height=12, wrap="word")
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

        ttk.Label(main, text="생성 결과 미리보기").pack(anchor="w")
        self.preview = tk.Text(main, height=16, wrap="word", state="disabled", bg="#f7f7f7")
        self.preview.pack(fill="both", expand=True, pady=(2, 8))

        self.save_btn = ttk.Button(
            main, text="Excel에 저장", command=self._on_save_clicked, state="disabled"
        )
        self.save_btn.pack(anchor="e")

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
        self._set_text(self.preview, "")

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
        self.current_tc_data = tc_data
        self._set_status("생성 완료. 내용 확인 후 저장하세요.")
        self._render_tc_preview(tc_data)
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
        self._set_text(self.preview, message)
        self.generate_btn.config(state="normal")
        messagebox.showerror("생성 실패", message)

    def _on_save_clicked(self):
        if not self.current_tc_data:
            return
        path = self.output_path.get().strip() or DEFAULT_OUTPUT_FILE
        try:
            tc_id = append_test_case(path, self.current_tc_data["bug_id"], self.current_tc_data)
        except Exception as e:
            messagebox.showerror("저장 실패", f"{type(e).__name__}: {e}")
            return

        self._set_status(f"저장 완료: {tc_id} -> {path}")
        messagebox.showinfo("저장 완료", f"{tc_id} 가(이) {path}에 저장되었습니다.")

    def _render_tc_preview(self, tc_data: dict):
        lines = [
            f"버그 번호   : {tc_data.get('bug_id')}",
            f"카테고리    : {tc_data.get('category')}",
            f"테스트 제목 : {tc_data.get('title')}",
            f"테스트 목적 : {tc_data.get('purpose')}",
            f"사전 조건   : {tc_data.get('precondition')}",
            f"입력값      : {tc_data.get('input_value')}",
            "테스트 절차 :",
        ]
        for i, step in enumerate(tc_data.get("steps", []), start=1):
            lines.append(f"  {i}. {step}")
        lines.append(f"기대결과    : {tc_data.get('expected')}")
        self._set_text(self.preview, "\n".join(lines))

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

        ttk.Label(main, text="생성된 버그 리포트 (Yona에 그대로 붙여넣기 가능)").pack(anchor="w")
        self.reverse_preview = tk.Text(main, height=16, wrap="word", state="disabled", bg="#f7f7f7")
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
        self.current_bug_report_text = None
        self._set_status_reverse("로컬 AI 모델 호출 중...")
        self._set_text(self.reverse_preview, "")

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
        self.current_bug_report_text = report
        self._set_status_reverse("생성 완료. 내용 확인 후 저장하세요.")
        self._set_text(self.reverse_preview, report)
        self.reverse_generate_btn.config(state="normal")
        self.reverse_save_btn.config(state="normal")

    def _on_reverse_error(self, message: str):
        self._set_status_reverse("생성 실패")
        self._set_text(self.reverse_preview, message)
        self.reverse_generate_btn.config(state="normal")
        messagebox.showerror("생성 실패", message)

    def _on_reverse_save_clicked(self):
        if not self.current_bug_report_text:
            return

        default_name = f"bugreport_{_sanitize_filename(self.current_bug_fields.get('title', ''))}.txt"
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
                f.write(self.current_bug_report_text)
        except Exception as e:
            messagebox.showerror("저장 실패", f"{type(e).__name__}: {e}")
            return

        self._set_status_reverse(f"저장 완료: {path}")
        messagebox.showinfo("저장 완료", f"파일이 저장되었습니다:\n{path}")

    # ==================================================================
    # 공용 표시 헬퍼
    # ==================================================================
    def _set_status(self, text: str):
        self.status_label.config(text=text)

    def _set_status_reverse(self, text: str):
        self.reverse_status_label.config(text=text)

    def _set_text(self, widget: tk.Text, text: str):
        widget.config(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.config(state="disabled")


def main():
    root = tk.Tk()
    app = TestCaseGeneratorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()