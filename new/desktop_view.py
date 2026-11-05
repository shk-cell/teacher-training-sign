"""윈도우 운영 화면의 색상과 레이아웃."""
import customtkinter as ctk
from PIL import Image, ImageDraw
from app_fonts import FONT_FAMILY, load_fonts

BG = "#F7F6F2"
INK = "#1E2938"
MUTED = "#77837D"
GREEN = "#23765F"
LINE = "#E7EAE3"
NAV = "#17352C"
FONT = FONT_FAMILY


def icon(kind, color="#FFFFFF", size=20):
    """작은 선 아이콘을 해상도에 맞춰 그립니다."""
    image = Image.new("RGBA", (80, 80))
    draw = ImageDraw.Draw(image)
    if kind == "book":
        draw.line([(40, 62), (40, 20), (18, 14), (13, 17), (13, 57), (40, 65), (67, 57), (67, 17), (62, 14), (40, 20)], fill=color, width=5, joint="curve")
    elif kind == "folder":
        draw.line([(12, 61), (12, 20), (31, 20), (38, 28), (67, 28), (67, 61), (12, 61)], fill=color, width=5, joint="curve")
        draw.line([(13, 35), (67, 35)], fill=color, width=4)
    elif kind == "grid":
        for x, y in [(15, 15), (46, 15), (15, 46), (46, 46)]:
            draw.rounded_rectangle((x, y, x+20, y+20), radius=4, outline=color, width=4)
    elif kind == "arrow":
        draw.line([(20, 60), (60, 20), (30, 20)], fill=color, width=5, joint="curve")
        draw.line([(60, 20), (60, 50)], fill=color, width=5)
    elif kind == "copy":
        draw.rounded_rectangle((27, 26, 62, 66), radius=6, outline=color, width=5)
        draw.line([(23, 53), (16, 53), (16, 15), (51, 15), (51, 21)], fill=color, width=5, joint="curve")
    elif kind == "shield":
        draw.line([(40, 12), (64, 22), (62, 46), (54, 59), (40, 68), (26, 59), (18, 46), (16, 22), (40, 12)], fill=color, width=5, joint="curve")
        draw.line([(28, 39), (37, 48), (53, 31)], fill=color, width=5, joint="curve")
    elif kind == "file":
        draw.line([(23, 12), (48, 12), (62, 27), (62, 66), (18, 66), (18, 12), (23, 12)], fill=color, width=5, joint="curve")
        draw.line([(46, 12), (46, 29), (62, 29)], fill=color, width=4)
        draw.line([(28, 42), (50, 42)], fill=color, width=4)
        draw.line([(28, 53), (44, 53)], fill=color, width=4)
    return ctk.CTkImage(image, size=(size, size))


def label(parent, text=None, *, size=13, color=INK, bold=False, **kwargs):
    return ctk.CTkLabel(parent, text=text, text_color=color, anchor="w",
                        font=(FONT, size, "bold" if bold else "normal"), **kwargs)


def button(parent, text, command, *, primary=False, image=None, **kwargs):
    return ctk.CTkButton(parent, text=text, command=command, height=42, corner_radius=9,
                         fg_color=GREEN if primary else "#F0F4F6",
                         hover_color="#1B614E" if primary else "#E5EBEE",
                         text_color="#FFFFFF" if primary else "#475565",
                         text_color_disabled="#98A69F", font=(FONT, 15, "bold"),
                         image=image, compound="left", **kwargs)


def card(parent):
    return ctk.CTkFrame(parent, fg_color="#FFFFFF", corner_radius=16,
                        border_width=1, border_color=LINE)


def build_window(app, root):
    load_fonts()
    ctk.set_appearance_mode("light")
    root.title("교직원 연수실")
    root.geometry("1100x810")
    root.minsize(1020, 760)
    root.configure(fg_color=BG)
    root.grid_columnconfigure(1, weight=1)
    root.grid_rowconfigure(0, weight=1)

    sidebar = ctk.CTkFrame(root, width=196, fg_color=NAV, corner_radius=0)
    sidebar.grid(row=0, column=0, sticky="nsew")
    sidebar.grid_propagate(False)
    sidebar.grid_columnconfigure(0, weight=1)
    sidebar.grid_rowconfigure(5, weight=1)
    brand = ctk.CTkFrame(sidebar, fg_color="transparent")
    brand.grid(row=0, column=0, sticky="ew", padx=24, pady=(32, 30))
    ctk.CTkLabel(brand, text="", image=icon("book", "#F1C58D", 36), width=40).pack(anchor="w")
    label(brand, "교직원 연수실", size=23, color="#FFFFFF", bold=True).pack(anchor="w", pady=(13, 5))
    label(brand, "학교 내부망 · 연수 관리", size=12, color="#A7BDB0").pack(anchor="w")

    ctk.CTkButton(sidebar, text="  운영 대시보드", image=icon("grid", "#C1E6D5"), anchor="w",
                  fg_color="#2B4640", hover_color="#2B4640", text_color="#E9F6EF", height=46,
                  corner_radius=9, font=(FONT, 15, "bold"), command=lambda: None).grid(row=1, column=0, sticky="ew", padx=16, pady=4)
    for row, text, name in [(2, "  연수자료 폴더", "연수자료"), (3, "  서명 저장 폴더", "data")]:
        ctk.CTkButton(sidebar, text=text, image=icon("folder", "#9FB6AE"), anchor="w",
                      fg_color="transparent", hover_color="#243D36", text_color="#BDD0C8", height=44,
                      corner_radius=9, font=(FONT, 14), command=lambda n=name: app.open_folder(n)).grid(row=row, column=0, sticky="ew", padx=16, pady=3)
    note = ctk.CTkFrame(sidebar, fg_color="#203A33", corner_radius=12)
    note.grid(row=6, column=0, sticky="ew", padx=20, pady=24)
    label(note, "이 창을 열어 두세요", size=14, color="#F1D8B6", bold=True).pack(anchor="w", padx=13, pady=(14, 6))
    label(note, "창을 닫으면 서버가 종료돼요.\n받은 서명은 그대로 보관돼요.", size=12, color="#A7BDB0", justify="left").pack(anchor="w", padx=13, pady=(0, 14))

    main = ctk.CTkFrame(root, fg_color="transparent", corner_radius=0)
    main.grid(row=0, column=1, sticky="nsew", padx=30, pady=26)
    main.grid_columnconfigure(0, weight=1)
    main.grid_rowconfigure(3, weight=1)
    heading = ctk.CTkFrame(main, fg_color="transparent")
    heading.grid(row=0, column=0, sticky="ew", pady=(0, 20))
    label(heading, "연수 관리", size=32, bold=True).pack(anchor="w")
    label(heading, "자료를 준비하고, 주소를 보내고, 서명을 확인하세요.", size=15, color=MUTED).pack(anchor="w", pady=(6, 0))

    server = card(main)
    server.grid(row=1, column=0, sticky="ew", pady=(0, 14))
    server.grid_columnconfigure(0, weight=1)
    state_row = ctk.CTkFrame(server, fg_color="transparent")
    state_row.grid(row=0, column=0, sticky="ew", padx=22, pady=(19, 4))
    app.status_pill = ctk.CTkLabel(state_row, text="●  준비 중", fg_color="#EDF2F5", text_color="#778597",
                                   corner_radius=12, height=25, width=90, font=(FONT, 11, "bold"))
    app.status_pill.pack(side="right")
    app.status_label = label(state_row, size=21, bold=True, textvariable=app.status)
    app.status_label.pack(side="left")
    label(server, size=13, color=MUTED, textvariable=app.detail, wraplength=680, justify="left").grid(row=1, column=0, sticky="w", padx=22, pady=(0, 12))
    controls = ctk.CTkFrame(server, fg_color="transparent")
    controls.grid(row=2, column=0, sticky="ew", padx=22, pady=(0, 19))
    label(controls, "포트", size=12, color=MUTED).pack(side="left", padx=(0, 10))
    app.port_entry = ctk.CTkEntry(controls, textvariable=app.port, width=80, height=36,
                                  corner_radius=7, fg_color="#F7F9FB", border_color=LINE,
                                  font=(FONT, 15), text_color=INK)
    app.port_entry.pack(side="left")
    label(controls, "중지한 뒤 변경할 수 있어요", size=12, color=MUTED).pack(side="left", padx=10)
    app.toggle_button = button(controls, "서버 시작", app.toggle, primary=True, width=110)
    app.toggle_button.pack(side="right")

    share = card(main)
    share.configure(fg_color="#F1F8F1", border_color="#D8E7D8")
    share.grid(row=2, column=0, sticky="ew", pady=(0, 14))
    share.grid_columnconfigure(0, weight=1)
    share_head = ctk.CTkFrame(share, fg_color="transparent")
    share_head.grid(row=0, column=0, sticky="ew", padx=22, pady=(17, 10))
    label(share_head, "02  참여 주소 공유", size=19, bold=True).pack(side="left")
    app.preview_button = ctk.CTkButton(share_head, text="화면 미리보기  ↗", width=115, height=28,
                                      fg_color="transparent", hover_color="#EDF5F1", text_color=GREEN,
                                      font=(FONT, 13, "bold"), command=lambda: app.open_browser(False))
    app.preview_button.pack(side="right")
    address_row = ctk.CTkFrame(share, fg_color="transparent")
    address_row.grid(row=1, column=0, sticky="ew", padx=22)
    address_row.grid_columnconfigure(0, weight=1)
    app.address_box = ctk.CTkOptionMenu(address_row, variable=app.address, values=[""], height=48,
                                       fg_color="#FFFFFF", button_color="#E1EEDF", button_hover_color="#D5E6D2",
                                       text_color="#264B40", dropdown_fg_color="#FFFFFF", dropdown_text_color=INK,
                                       dropdown_hover_color="#EDF5F1", font=(FONT, 19), dropdown_font=(FONT, 16), corner_radius=9)
    app.address_box.grid(row=0, column=0, sticky="ew", padx=(0, 10))
    app.copy_button = button(address_row, "주소 복사", lambda: app.copy(app.address.get(), "참여 주소를 복사했습니다."),
                              primary=True, image=icon("copy"), width=122)
    app.copy_button.grid(row=0, column=1, ipady=3)
    label(share, "주소를 복사해 교내 메신저로 보내 주세요. 같은 학교 네트워크에서 참여할 수 있어요.",
          size=12, color=MUTED, wraplength=720).grid(row=2, column=0, sticky="w", padx=22, pady=(10, 17))

    bottom = ctk.CTkFrame(main, fg_color="transparent")
    bottom.grid(row=3, column=0, sticky="nsew")
    bottom.grid_columnconfigure((0, 1), weight=1, uniform="cards")
    bottom.grid_rowconfigure(0, weight=1)
    materials = card(bottom)
    materials.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
    admin = card(bottom)
    admin.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
    for panel in (materials, admin):
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(3, weight=1)
    label(materials, "01  연수자료 준비", size=19, bold=True).grid(row=0, column=0, sticky="w", padx=22, pady=(19, 9))
    label(materials, "자료 폴더에 파일을 넣어 주세요.", size=15, color="#556273").grid(row=1, column=0, sticky="w", padx=22)
    label(materials, "PDF·PNG 변경이 자동으로 반영돼요.\n여러 장은 한 폴더에 묶어 주세요.", size=13, color=MUTED, justify="left").grid(row=2, column=0, sticky="w", padx=22, pady=(7, 12))
    button(materials, "자료 폴더 열기", lambda: app.open_folder("연수자료"),
           image=icon("folder", "#475565")).grid(row=4, column=0, sticky="ew", padx=22, pady=(0, 20))

    admin_head = ctk.CTkFrame(admin, fg_color="transparent")
    admin_head.grid(row=0, column=0, sticky="ew", padx=22, pady=(19, 9))
    label(admin_head, "03  서명 확인", size=19, bold=True).pack(side="left")
    ctk.CTkCheckBox(admin_head, text="표시", variable=app.reveal, width=52,
                    checkbox_width=15, checkbox_height=15, corner_radius=4, border_width=1,
                    border_color="#C5CFD6", fg_color=GREEN, hover_color="#DCEAE2", text_color=MUTED,
                    font=(FONT, 12), command=lambda: app.password_entry.configure(show="" if app.reveal.get() else "•")).pack(side="right")
    password_row = ctk.CTkFrame(admin, fg_color="transparent")
    password_row.grid(row=1, column=0, sticky="ew", padx=22)
    password_row.grid_columnconfigure(0, weight=1)
    app.password_entry = ctk.CTkEntry(password_row, textvariable=app.password, show="•", state="readonly",
                                      height=38, corner_radius=7, fg_color="#F7F9FB", border_color=LINE,
                                      text_color="#4E5D70", font=(FONT, 16))
    app.password_entry.grid(row=0, column=0, sticky="ew", padx=(0, 7))
    app.password_copy = button(password_row, "복사", lambda: app.copy(app.password.get(), "관리자 비밀번호를 복사했습니다."), width=58)
    app.password_copy.grid(row=0, column=1)
    label(admin, "위 비밀번호로 관리자 화면에 로그인해요.", size=13, color=MUTED).grid(row=2, column=0, sticky="w", padx=22, pady=(8, 12))
    app.admin_button = button(admin, "관리자 화면 열기  ↗", lambda: app.open_browser(True), primary=True)
    app.admin_button.grid(row=4, column=0, sticky="ew", padx=22, pady=(0, 20))

    app.feedback_label = label(main, size=11, color=GREEN, textvariable=app.feedback)
    app.feedback_label.grid(row=4, column=0, sticky="w", pady=(10, 0))
    footer = ctk.CTkFrame(main, fg_color="transparent")
    footer.grid(row=5, column=0, sticky="ew", pady=(3, 0))
    label(footer, "자료와 서명은 이 컴퓨터에 저장됩니다.", size=10, color=MUTED).pack(side="left")
    label(footer, "교직원 연수실", size=10, color="#A8B2BD").pack(side="right")
