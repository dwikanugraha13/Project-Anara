import os
from fpdf import FPDF

class AnaraDossierPDF(FPDF):
    def header(self):
        # Top banner background
        self.set_fill_color(15, 23, 42) # Slate 900
        self.rect(0, 0, 210, 36, 'F')
        
        # Indigo accent bar
        self.set_fill_color(99, 102, 241) # Indigo 500
        self.rect(0, 36, 210, 3, 'F')
        
        # Header title
        self.set_text_color(255, 255, 255)
        self.set_font('Helvetica', 'B', 15)
        self.set_xy(16, 9)
        self.cell(0, 7, 'PROJECT ANARA | DEVELOPER DOSSIER', 0, 1, 'L')
        
        # Subtitle badge
        self.set_font('Helvetica', '', 9)
        self.set_text_color(165, 180, 252) # Indigo 200
        self.set_xy(16, 17)
        self.cell(0, 6, 'Edisi Santai Khusus Agnan - Generated Autonomously by Anara', 0, 1, 'L')
        
        self.set_text_color(148, 163, 184) # Slate 400
        self.set_xy(16, 24)
        self.cell(0, 6, 'Waktu Pembuatan: Selasa, 29 September 2026 | Format: A4 Universal', 0, 1, 'L')

    def footer(self):
        self.set_y(-16)
        self.set_font('Helvetica', '', 8)
        self.set_text_color(148, 163, 184)
        # Separator line
        self.set_draw_color(226, 232, 240)
        self.line(16, 280, 194, 280)
        self.cell(0, 10, f'Project Anara Environment  |  Halaman {self.page_no()}', 0, 0, 'C')

def build_pdf():
    pdf = AnaraDossierPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()
    
    # Hero Intro Card
    pdf.set_xy(16, 44)
    pdf.set_fill_color(248, 250, 252)
    pdf.set_draw_color(203, 213, 225)
    pdf.rect(16, 44, 178, 30, 'DF')
    
    pdf.set_xy(20, 48)
    pdf.set_font('Helvetica', 'B', 11)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 5, 'Halo Agnan! Berkas Santai Permintaan Lu Udah Mendarat', 0, 1)
    
    pdf.set_xy(20, 55)
    pdf.set_font('Helvetica', '', 9)
    pdf.set_text_color(71, 85, 105)
    intro_text = (
        "Lu minta bikinin file PDF dengan isi bebas, jadi gue racik dokumen spesial yang estetik "
        "sekaligus berfaedah. Dokumen ini merangkum status runtime, mantra ngoding lu-gue, cheatsheet sakti, "
        "dan catatan santai buat nemenin sesi hacking lu kapanpun lu butuh referensi cepat."
    )
    pdf.multi_cell(170, 4.5, intro_text)
    
    # Section 1: Profil & Parameter Sistem
    pdf.set_xy(16, 80)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 7, '1. Status Ekosistem & Profil Runtime', 0, 1)
    
    # Specs Table / Grid
    pdf.set_fill_color(241, 245, 249)
    pdf.rect(16, 88, 178, 42, 'F')
    
    specs = [
        ("Owner & Lead Developer", "Agnan"),
        ("Autonomous AI Companion", "Anara (Multimodal 3D Desktop Agent)"),
        ("Operational Gateway", "Web Studio & Code Studio Suite"),
        ("Active Host Path", "C:\\Users\\Bravo\\Documents\\Project Anara"),
        ("Runtime Orchestration", "Python 3.14 & Node.js / Vite / Tailwind"),
        ("Staging Environment", "Docker Swarm Runner (Auto-Healing)")
    ]
    
    row_y = 91
    for label, val in specs:
        pdf.set_xy(20, row_y)
        pdf.set_font('Helvetica', 'B', 8.5)
        pdf.set_text_color(71, 85, 105)
        pdf.cell(55, 5, label, 0, 0)
        pdf.set_font('Helvetica', '', 8.5)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(0, 5, f":  {val}", 0, 1)
        row_y += 6

    # Section 2: Filosofi Ngoding Santai tapi Nendang
    pdf.set_xy(16, 136)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 7, '2. Kaidah Ngoding Anti-Pusing (Anara Way)', 0, 1)
    
    principles = [
        ("Prinsip 1: Ground Truth over Asumsi", "Jangan nebak error atau asumsi kode jalan sebelum dites. Selalu verifikasi langsung di terminal dengan exit code 0."),
        ("Prinsip 2: Clean & Modular First", "Pecah logic rumit ke modul kecil yang independen. Kodingan yang rapi bikin debugging 10x lebih cepat."),
        ("Prinsip 3: Keep It Simple & Santai", "Nggak usah overcomplicate arsitektur buat hal-hal sederhana. Bikin yang efektif, fungsional, baru di-polish."),
        ("Prinsip 4: Otomasi Hal Boring", "Semua yang repetitif kayak bikin file boilerplate, tes rutin, atau deploy staging serahin ke script atau asisten.")
    ]
    
    curr_y = 145
    for title, desc in principles:
        pdf.set_xy(16, curr_y)
        pdf.set_fill_color(248, 250, 252)
        pdf.set_draw_color(226, 232, 240)
        pdf.rect(16, curr_y, 178, 12, 'DF')
        
        pdf.set_xy(20, curr_y + 1.5)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_text_color(79, 70, 229) # Indigo 600
        pdf.cell(56, 4.5, title, 0, 0)
        pdf.set_font('Helvetica', '', 8.5)
        pdf.set_text_color(51, 65, 85)
        pdf.cell(0, 4.5, f"- {desc}", 0, 1)
        curr_y += 14

    # Section 3: Cheatsheet Terminal & Dev Ops Sakti
    pdf.set_xy(16, 206)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 7, '3. Cheatsheet Command Favorit', 0, 1)
    
    pdf.set_fill_color(15, 23, 42) # Slate 900 code box
    pdf.rect(16, 214, 178, 38, 'F')
    
    commands = [
        ("# 1. Verifikasi test suite cepat", "python run_tests.py"),
        ("# 2. Cek status git worktree & branch", "git status -sb"),
        ("# 3. Pantau log proses aktif real-time", "Get-Process | Sort-Object CPU -Descending | Select-Object -First 5"),
        ("# 4. Inspect port listening di Windows", "netstat -ano | findstr :8080")
    ]
    
    cmd_y = 217
    for desc, cmd in commands:
        pdf.set_xy(20, cmd_y)
        pdf.set_font('Courier', '', 8)
        pdf.set_text_color(148, 163, 184) # Comment
        pdf.cell(65, 4, desc, 0, 0)
        pdf.set_font('Courier', 'B', 8.5)
        pdf.set_text_color(56, 189, 248) # Cyan 400
        pdf.cell(0, 4, f"> {cmd}", 0, 1)
        cmd_y += 8

    # Final Quote Box
    pdf.set_xy(16, 256)
    pdf.set_fill_color(238, 242, 255) # Indigo 50
    pdf.set_draw_color(199, 210, 254)
    pdf.rect(16, 256, 178, 18, 'DF')
    
    pdf.set_xy(20, 259)
    pdf.set_font('Helvetica', 'I', 9)
    pdf.set_text_color(67, 56, 202)
    pdf.cell(0, 5, '"Kode terbaik adalah kode yang lu tulis dengan kepala dingin, hati tenang, dan kopi di samping." ', 0, 1, 'C')
    pdf.set_font('Helvetica', 'B', 8)
    pdf.set_text_color(99, 102, 241)
    pdf.cell(0, 4.5, '- Anara AI Companion', 0, 1, 'C')

    output_filename = "catatan_santai_anara.pdf"
    pdf.output(output_filename)
    print(f"File PDF berhasil dibuat: {os.path.abspath(output_filename)}")

if __name__ == '__main__':
    build_pdf()
