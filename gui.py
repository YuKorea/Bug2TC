"""
gui.py
AI 기반 Test Case Generator - Tkinter GUI (V1 대체 실행 방식)

main.py(CLI)와 동일한 로직(ai_client, excel_writer)을 그대로 재사용합니다.
API 호출은 백그라운드 스레드에서 실행해서 UI가 멈추지 않도록 처리했습니다.

실행: python gui.py
"""

import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from ai_client import generate_test_case
from excel_writer import append_test_case, COLUMNS
from paths import get_desktop_path

DEFAULT_OUTPUT_FILE = str(get_desktop_path() / "testcase.xlsx")


class TestCaseGeneratorApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("AI 기반 Test Case Generator")
        self.root.geometry("900x720")

        self.current_tc_data = None  # 마지막으로 생성된 테스트케이스 (저장용)
        self.output_path = tk.StringVar(value=DEFAULT_OUTPUT_FILE)

        self._build_layout()

    # ------------------------------------------------------------------
    # 레이아웃 구성
    # ------------------------------------------------------------------
    def _build_layout(self):
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)

        # --- 상단: 출력 파일 경로 ---
        path_frame = ttk.Frame(main)
        path_frame.pack(fill="x", pady=(0, 8))

        ttk.Label(path_frame, text="저장 파일:").pack(side="left")
        ttk.Entry(path_frame, textvariable=self.output_path, width=50).pack(
            side="left", padx=6
        )
        ttk.Button(path_frame, text="찾아보기", command=self._browse_output_file).pack(
            side="left"
        )

        # --- Yona 버그 리포트 입력 ---
        ttk.Label(main, text="Yona 버그 리포트 (제목, 버그 설명, 재현 스텝, 기대 결과 등 통째로 붙여넣기)").pack(
            anchor="w"
        )
        self.bug_input = tk.Text(main, height=12, wrap="word")
        self.bug_input.pack(fill="both", expand=False, pady=(2, 8))

        # --- 시나리오 힌트 (선택) ---
        hint_frame = ttk.Frame(main)
        hint_frame.pack(fill="x", pady=(0, 8))
        ttk.Label(hint_frame, text="시나리오 힌트 (선택, 예: 공백만 입력하는 케이스만):").pack(
            side="left"
        )
        self.scenario_hint = tk.StringVar()
        ttk.Entry(hint_frame, textvariable=self.scenario_hint, width=45).pack(
            side="left", padx=6
        )

        # --- 실행 버튼 + 상태 ---
        action_frame = ttk.Frame(main)
        action_frame.pack(fill="x", pady=(0, 8))

        self.generate_btn = ttk.Button(
            action_frame, text="테스트 케이스 생성", command=self._on_generate_clicked
        )
        self.generate_btn.pack(side="left")

        self.status_label = ttk.Label(action_frame, text="", foreground="#555555")
        self.status_label.pack(side="left", padx=12)

        # --- 미리보기 ---
        ttk.Label(main, text="생성 결과 미리보기").pack(anchor="w")
        self.preview = tk.Text(main, height=16, wrap="word", state="disabled", bg="#f7f7f7")
        self.preview.pack(fill="both", expand=True, pady=(2, 8))

        # --- 저장 버튼 ---
        self.save_btn = ttk.Button(
            main, text="Excel에 저장", command=self._on_save_clicked, state="disabled"
        )
        self.save_btn.pack(anchor="e")

    # ------------------------------------------------------------------
    # 이벤트 핸들러
    # ------------------------------------------------------------------
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
        self._set_preview("")

        # UI가 멈추지 않도록 API 호출은 별도 스레드에서 실행
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
        self._render_preview(tc_data)
        self.generate_btn.config(state="normal")
        self.save_btn.config(state="normal")

    def _on_generate_error(self, message: str):
        self._set_status("생성 실패")
        self._set_preview(message)
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

    # ------------------------------------------------------------------
    # 표시 헬퍼
    # ------------------------------------------------------------------
    def _set_status(self, text: str):
        self.status_label.config(text=text)

    def _set_preview(self, text: str):
        self.preview.config(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", text)
        self.preview.config(state="disabled")

    def _render_preview(self, tc_data: dict):
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
        self._set_preview("\n".join(lines))


def main():
    root = tk.Tk()
    app = TestCaseGeneratorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
