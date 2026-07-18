import mido
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import shutil
import sys
import threading

# =====================================================================
# CORE ENGINE: LOGIKA REMAPPER DENGAN PROTEKSI CASM & OTS
# =====================================================================

def perbaiki_dan_salin_casm(file_asli, file_hasil_remap):
    try:
        with open(file_asli, 'rb') as f:
            data_asli = f.read()
        
        with open(file_hasil_remap, 'rb') as f:
            data_remap = f.read()

        idx_casm = data_asli.find(b'CASM')
        if idx_casm == -1:
            pos = 0
            last_mtrk = -1
            while True:
                pos = data_asli.find(b'MTrk', pos)
                if pos == -1: break
                last_mtrk = pos
                pos += 4
            
            if last_mtrk != -1:
                length = int.from_bytes(data_asli[last_mtrk+4:last_mtrk+8], byteorder='big')
                idx_casm = last_mtrk + 8 + length
            else:
                return False

        ekor_yamaha = data_asli[idx_casm:]
        if ekor_yamaha:
            with open(file_hasil_remap, 'wb') as f:
                f.write(data_remap + ekor_yamaha)
            return True
    except:
        return False
    return False

def proses_remap_otomatis_core(file_input, path_output_spesifik, msb_lama_target, lsb_lama_target, lsb_baru):
    try:
        mid = mido.MidiFile(file_input)
        perubahan_terjadi = False

        for track in mid.tracks:
            current_bank = {ch: {'msb': None, 'lsb': None, 'msg_msb': None, 'msg_lsb': None} for ch in range(16)}
            
            for msg in track:
                if not hasattr(msg, 'channel'):
                    continue
                ch = msg.channel

                if msg.type == 'control_change' and msg.control == 0:
                    current_bank[ch]['msb'] = msg.value
                    current_bank[ch]['msg_msb'] = msg

                elif msg.type == 'control_change' and msg.control == 32:
                    current_bank[ch]['lsb'] = msg.value
                    current_bank[ch]['msg_lsb'] = msg

                elif msg.type == 'program_change':
                    c_msb = current_bank[ch]['msb']
                    c_lsb = current_bank[ch]['lsb']
                    
                    msb_cocok = False
                    if msb_lama_target is None:
                        if c_msb in [62, 63]: msb_cocok = True
                    else:
                        if c_msb == msb_lama_target: msb_cocok = True
                            
                    lsb_cocok = False
                    if lsb_lama_target is None:
                        lsb_cocok = True 
                    else:
                        if c_lsb == lsb_lama_target: lsb_cocok = True
                    
                    if msb_cocok and lsb_cocok:
                        if current_bank[ch]['msg_lsb']: 
                            current_bank[ch]['msg_lsb'].value = lsb_baru
                        perubahan_terjadi = True
                        
        if perubahan_terjadi:
            mid.save(path_output_spesifik)
            perbaiki_dan_salin_casm(file_input, path_output_spesifik)
            return "BERHASIL"
        else:
            shutil.copy2(file_input, path_output_spesifik)
            return "LEWAT"
    except Exception as e:
        return f"ERROR: {str(e)}"

def scan_voice_style_core(file_input):
    list_voice = []
    try:
        mid = mido.MidiFile(file_input)
        for track_idx, track in enumerate(mid.tracks):
            current_bank = {ch: {'msb': 0, 'lsb': 0} for ch in range(16)}
            nama_trek = track.name if hasattr(track, 'name') else f"Trek {track_idx}"
            
            for msg in track:
                if not hasattr(msg, 'channel'): continue
                ch = msg.channel

                if msg.type == 'control_change' and msg.control == 0:
                    current_bank[ch]['msb'] = msg.value
                elif msg.type == 'control_change' and msg.control == 32:
                    current_bank[ch]['lsb'] = msg.value
                elif msg.type == 'program_change':
                    msb = current_bank[ch]['msb']
                    lsb = current_bank[ch]['lsb']
                    pc = msg.program + 1
                    kategori = "EXPANSION" if msb in [62, 63] else "PRESET"
                    
                    list_voice.append({
                        'track': nama_trek, 'channel': ch + 1,
                        'msb': msb, 'lsb': lsb, 'pc': pc, 'kategori': kategori
                    })
        return list_voice
    except Exception as e:
        return f"ERROR: {str(e)}"

# =====================================================================
# INTERFACE GUI UTAMA
# =====================================================================

class YamahaStyleToolkit:
    def __init__(self, root):
        self.root = root
        self.root.title("Yamaha Style Toolkit (Strict Folder Isolation)")
        self.root.geometry("760x600")
        self.root.resizable(False, False)

        if getattr(sys, 'frozen', False):
            self.root_dir = os.path.dirname(sys.executable)
        else:
            self.root_dir = os.path.dirname(os.path.abspath(__file__))

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)

        self.tab_remap = ttk.Frame(self.notebook)
        self.tab_scan = ttk.Frame(self.notebook)
        
        self.notebook.add(self.tab_remap, text="  1. Deep Voice Remapper (LSB)  ")
        self.notebook.add(self.tab_scan, text="  2. Deep Voice Scanner  ")

        self.root_folder_input = ""
        self.nama_folder_input_asli = ""
        self.path_parent_input = ""
        self.mode_input = "file"

        self.setup_tab_remap()
        self.setup_tab_scan()

    def setup_tab_remap(self):
        self.remap_files_dict = {}
        self.txt_remap_sumber = tk.StringVar(value="Belum ada file dipilih.")

        frame_input = tk.LabelFrame(self.tab_remap, text=" Pengaturan Input Style (Mendukung Sub-Folder Berlapis) ", padx=10, pady=10)
        frame_input.pack(fill="x", padx=15, pady=10)

        tk.Entry(frame_input, textvariable=self.txt_remap_sumber, width=65, state="readonly").grid(row=0, column=0, columnspan=2, padx=5, pady=5)
        tk.Button(frame_input, text="Pilih Folder Root (Scan Deep)", width=22, command=lambda: self.pilih_sumber("remap", "folder")).grid(row=1, column=0, padx=5, pady=5)
        tk.Button(frame_input, text="Pilih File Manual (Block)", width=22, command=lambda: self.pilih_sumber("remap", "file")).grid(row=1, column=1, padx=5, pady=5)

        frame_param = tk.LabelFrame(self.tab_remap, text=" Parameter Bank Voice (Cari Kriteria & Ubah LSB) ", padx=10, pady=10)
        frame_param.pack(fill="x", padx=15, pady=5)

        tk.Label(frame_param, text="Cari MSB Lama:").grid(row=0, column=0, sticky="w")
        self.entry_msb_lama = tk.Entry(frame_param, width=8, bg="#fffde7")
        self.entry_msb_lama.grid(row=0, column=1, padx=5, sticky="w")

        tk.Label(frame_param, text="Cari LSB Lama:").grid(row=0, column=2, sticky="w", padx=15)
        self.entry_lsb_lama = tk.Entry(frame_param, width=8, bg="#fffde7")
        self.entry_lsb_lama.grid(row=0, column=3, padx=5, sticky="w")
        
        tk.Label(frame_param, text="*(Kosongkan = OTOMATIS deteksi MSB 62/63 & Semua LSB)", fg="#d35400", font=("Arial", 9, "italic")).grid(row=1, column=0, columnspan=4, sticky="w", pady=2)

        tk.Label(frame_param, text="Ubah ke LSB Baru:").grid(row=2, column=0, sticky="w", pady=8)
        self.entry_lsb_baru = tk.Entry(frame_param, width=12, font=("Arial", 10, "bold"), fg="blue")
        self.entry_lsb_baru.grid(row=2, column=1, padx=5, pady=8, sticky="w")
        self.entry_lsb_baru.insert(0, "4")

        tk.Button(self.tab_remap, text="REFRESH INPUT / RE-SCAN DATA", bg="#f39c12", fg="white", font=("Arial", 9, "bold"), command=self.refresh_sumber_remap).pack(anchor="e", padx=15, pady=2)

        self.btn_action_remap = tk.Button(self.tab_remap, text="MULAI REMAP MASSAL SEMUA SUB-FOLDER", bg="#2ecc71", fg="white", font=("Arial", 11, "bold"), pady=6, command=self.picu_thread_remap)
        self.btn_action_remap.pack(fill="x", padx=15, pady=5)

        tk.Label(self.tab_remap, text="Monitor Aktivitas Deep Remap (Live Progress Log):").pack(anchor="w", padx=15)
        self.log_remap = tk.Text(self.tab_remap, height=10, width=87, state="disabled", bg="#1e272e", fg="#ffffff")
        self.log_remap.pack(padx=15, pady=5)

    def refresh_sumber_remap(self):
        """Fitur untuk memaksa re-scan folder apabila kamu menghapus folder sisa remap secara manual"""
        if self.mode_input == "folder" and self.root_folder_input:
            self.pembacaan_deep_folder_recursif("remap", self.root_folder_input)
            messagebox.showinfo("Refreshed", "Data antrean file berhasil diperbarui!")
        else:
            messagebox.showwarning("Perhatian", "Refresh hanya berlaku untuk input mode Folder.")

    def picu_thread_remap(self):
        t = threading.Thread(target=self.eksekusi_remap)
        t.daemon = True
        t.start()

    def eksekusi_remap(self):
        if not self.remap_files_dict:
            messagebox.showerror("Error", "Pilih folder root atau block file terlebih dahulu!")
            return

        self.btn_action_remap.config(state="disabled", text="SEDANG MEMPROSES FILE...")

        val_msb_l = self.entry_msb_lama.get().strip()
        val_lsb_l = self.entry_lsb_lama.get().strip()
        
        msb_target = int(val_msb_l) if val_msb_l else None
        lsb_target = int(val_lsb_l) if val_lsb_l else None

        try:
            l_baru = int(self.entry_lsb_baru.get())
        except ValueError:
            messagebox.showerror("Error", "Nilai Target LSB Baru wajib diisi angka!")
            self.btn_action_remap.config(state="normal", text="MULAI REMAP MASSAL SEMUA SUB-FOLDER")
            return

        if self.mode_input == "folder":
            nama_folder_induk_baru = f"{l_baru}_{self.nama_folder_input_asli}"
            base_output_dir = os.path.join(self.path_parent_input, nama_folder_induk_baru)
        else:
            first_file = list(self.remap_files_dict.keys())[0]
            base_output_dir = os.path.join(os.path.dirname(first_file), f"{l_baru}_REMAP_MANUAL_BLOCK")

        self.update_log(self.log_remap, "clear")
        self.update_log(self.log_remap, f"--- Memulai Deep Recursive Remap LSB ({len(self.remap_files_dict)} File) ---")
        self.update_log(self.log_remap, f"Folder Induk Baru: {base_output_dir}\n")
        
        sukses, lewat = 0, 0
        total_file = len(self.remap_files_dict)
        
        for idx, (path_file_asli, rel_path) in enumerate(self.remap_files_dict.items(), start=1):
            path_output_spesifik = os.path.join(base_output_dir, rel_path)
            
            sub_folder_target = os.path.dirname(path_output_spesifik)
            if not os.path.exists(sub_folder_target):
                os.makedirs(sub_folder_target)
                
            hasil = proses_remap_otomatis_core(path_file_asli, path_output_spesifik, msb_target, lsb_target, l_baru)
            
            if hasil == "BERHASIL":
                self.update_log(self.log_remap, f"[{idx}/{total_file}] [✓] DIREMAP LSB ➔ {rel_path}")
                sukses += 1
            else:
                self.update_log(self.log_remap, f"[{idx}/{total_file}] [-] PRESET UTUH ➔ {rel_path}")
                lewat += 1
                
            self.root.update_idletasks()

        self.update_log(self.log_remap, f"\n=== PROSES DEEP REMAP SELESAI ===")
        self.btn_action_remap.config(state="normal", text="MULAI REMAP MASSAL SEMUA SUB-FOLDER")
        messagebox.showinfo("Selesai", f"Deep Remap Selesai!\nLokasi Induk:\n{base_output_dir}")

    def setup_tab_scan(self):
        self.scan_files_list = []
        self.txt_scan_sumber = tk.StringVar(value="Belum ada file dipilih.")

        frame_input = tk.LabelFrame(self.tab_scan, text=" Pengaturan Input Style (Mendukung Scan Deep Sub-Folder) ", padx=10, pady=10)
        frame_input.pack(fill="x", padx=15, pady=10)

        tk.Entry(frame_input, textvariable=self.txt_scan_sumber, width=65, state="readonly").grid(row=0, column=0, columnspan=2, padx=5, pady=5)
        tk.Button(frame_input, text="Pilih Folder Root (Scan Deep)", width=22, command=lambda: self.pilih_sumber("scan", "folder")).grid(row=1, column=0, padx=5, pady=5)
        tk.Button(frame_input, text="Pilih File Manual (Block)", width=22, command=lambda: self.pilih_sumber("scan", "file")).grid(row=1, column=1, padx=5, pady=5)

        self.btn_action_scan = tk.Button(self.tab_scan, text="MULAI DEEP SCAN LIVE (HANYA SUARA EXPANSION)", bg="#3498db", fg="white", font=("Arial", 11, "bold"), pady=8, command=self.picu_thread_scan)
        self.btn_action_scan.pack(fill="x", padx=15, pady=10)

        frame_tabel = tk.LabelFrame(self.tab_scan, text=" Hasil Pemindaian (Hanya Khusus Custom Expansion) ", padx=10, pady=5)
        frame_tabel.pack(fill="both", expand=True, padx=15, pady=5)

        kolom = ("file", "track", "channel", "msb", "lsb", "pc", "format", "kategori")
        self.tabel_scan = ttk.Treeview(frame_tabel, columns=kolom, show="headings", height=10)
        
        self.tabel_scan.heading("file", text="Nama File")
        self.tabel_scan.heading("track", text="Nama Trek")
        self.tabel_scan.heading("channel", text="Ch")
        self.tabel_scan.heading("msb", text="MSB")
        self.tabel_scan.heading("lsb", text="LSB")
        self.tabel_scan.heading("pc", text="PC")
        self.tabel_scan.heading("format", text="Format (M-L-P)")
        self.tabel_scan.heading("kategori", text="Kategori")

        self.tabel_scan.column("file", width=140, anchor="w")
        self.tabel_scan.column("track", width=90, anchor="w")
        self.tabel_scan.column("channel", width=40, anchor="center")
        self.tabel_scan.column("msb", width=50, anchor="center")
        self.tabel_scan.column("lsb", width=50, anchor="center")
        self.tabel_scan.column("pc", width=50, anchor="center")
        self.tabel_scan.column("format", width=100, anchor="center")
        self.tabel_scan.column("kategori", width=100, anchor="center")

        scrollbar_v = ttk.Scrollbar(frame_tabel, orient="vertical", command=self.tabel_scan.yview)
        self.tabel_scan.configure(yscrollcommand=scrollbar_v.set)
        
        self.tabel_scan.pack(side="left", fill="both", expand=True)
        scrollbar_v.pack(side="right", fill="y")

        self.tabel_scan.tag_configure("expansion", background="#ffebee", foreground="#c62828")

    def picu_thread_scan(self):
        t = threading.Thread(target=self.eksekusi_scan)
        t.daemon = True
        t.start()

    def eksekusi_scan(self):
        if not self.scan_files_list:
            messagebox.showerror("Error", "Pilih folder root atau block file terlebih dahulu!")
            return

        self.btn_action_scan.config(state="disabled", text="SEDANG MEMINDAI MASSAL...")

        for i in self.tabel_scan.get_children():
            self.tabel_scan.delete(i)

        path_laporan = os.path.join(self.root_dir, "Laporan_Scan_Voice_Style.txt")
        total_exp = 0
        file_terdeteksi_count = 0
        
        with open(path_laporan, "w", encoding="utf-8") as f_rep:
            f_rep.write("===================================================\n")
            f_rep.write("   LAPORAN DEEP VOICE EXPANSION SCAN (FILTERED)    \n")
            f_rep.write("===================================================\n\n")

            for path_file in self.scan_files_list:
                nama = os.path.basename(path_file)
                data = scan_voice_style_core(path_file)
                
                if isinstance(data, str) and data.startswith("ERROR"):
                    f_rep.write(f"FILE: {nama} ➔ [CORRUPT/GAGAL BACA]\n\n")
                    continue
                
                punya_expansion = any(item['kategori'] == "EXPANSION" for item in data)
                
                if punya_expansion:
                    file_terdeteksi_count += 1
                    f_rep.write(f"FILE: {path_file}\n" + "-"*60 + "\n")
                    
                    for item in data:
                        if item['kategori'] == "EXPANSION":
                            total_exp += 1
                            format_gabungan = f"{item['msb']}-{item['lsb']}-{item['pc']}"
                            
                            self.tabel_scan.insert("", "end", values=(
                                nama, 
                                item['track'], 
                                item['channel'], 
                                item['msb'], 
                                item['lsb'], 
                                item['pc'], 
                                format_gabungan, 
                                item['kategori']
                            ), tags=("expansion",))
                            
                            f_rep.write(f"  [{item['track']}] Ch {item['channel']:02d} | MSB: {item['msb']:3d} | LSB: {item['lsb']:3d} | PC: {item['pc']:3d} | Format: {format_gabungan}\n")
                    
                    f_rep.write("\n" + "="*60 + "\n\n")
                    
                self.root.update_idletasks()
            
            f_rep.write(f"\n=== SUMMARY FILTRATION ===\n")
            f_rep.write(f"Total File Diperiksa secara Deep: {len(self.scan_files_list)}\n")
            f_rep.write(f"File Berisi Data Expansion      : {file_terdeteksi_count}\n")
            f_rep.write(f"Total Komponen Voice Expansion  : {total_exp}\n")

        self.btn_action_scan.config(state="normal", text="MULAI DEEP SCAN LIVE (HANYA SUARA EXPANSION)")
        messagebox.showinfo("Scan Selesai", f"Deep Pemindaian Berhasil!\n\n• {total_exp} Voice Expansion ditampilkan.\n• Laporan teks dibuat di root program:\n{path_laporan}")

    # -----------------------------------------------------------------
    # CORE RECURSIVE FUNCTION DENGAN SISTEM ISOLASI FOLDER HASIL
    # -----------------------------------------------------------------
    def pembacaan_deep_folder_recursif(self, tab_name, folder_path):
        valid_ext = ('.sty', '.prs', '.sst', '.vce')
        files_found_dict = {}
        files_found_list = []
        
        # ISOLASI: os.walk menyisir folder
        for root_dir, dirs, files in os.walk(folder_path):
            # FILTER FIX: Blokir os.walk agar tidak membaca folder hasil konversi lama yang ada di lokasi itu
            # Menghapus folder tujuan lama dari daftar penelusuran secara dinamis
            dirs[:] = [d for d in dirs if not (d.split('_')[0].isdigit() and len(d.split('_')) > 1)]
            
            for file in files:
                if file.lower().endswith(valid_ext):
                    full_path = os.path.join(root_dir, file)
                    rel_path = os.path.relpath(full_path, folder_path)
                    
                    files_found_dict[full_path] = rel_path
                    files_found_list.append(full_path)
                    
        desc = f"Root Folder: {os.path.basename(folder_path)} ({len(files_found_list)} file)"
        
        if tab_name == "remap":
            self.remap_files_dict = files_found_dict
            self.txt_remap_sumber.set(desc)
        else:
            self.scan_files_list = files_found_list
            self.txt_scan_sumber.set(desc)

    def pilih_sumber(self, tab_name, input_type):
        if input_type == "folder":
            folder = filedialog.askdirectory()
            if not folder: return
            
            folder_clean = os.path.normpath(folder)
            if tab_name == "remap":
                self.mode_input = "folder"
                self.root_folder_input = folder_clean
                self.path_parent_input = os.path.dirname(folder_clean)
                self.nama_folder_input_asli = os.path.basename(folder_clean)
                
            self.pembacaan_deep_folder_recursif(tab_name, folder_clean)
                
        else:
            files = filedialog.askopenfilenames(title="Block File Style", filetypes=[("Yamaha Files", "*.sty *.prs *.sst *.vce")])
            if not files: return
            
            files = list(files)
            desc = f"Manual Block: {len(files)} file dipilih."
            
            if tab_name == "remap":
                self.mode_input = "file"
                self.remap_files_dict = {f: os.path.basename(f) for f in files}
                self.txt_remap_sumber.set(desc)
            else:
                self.scan_files_list = files
                self.txt_scan_sumber.set(desc)

    def update_log(self, text_widget, pesan):
        text_widget.configure(state="normal")
        if pesan == "clear":
            text_widget.delete("1.0", tk.END)
        else:
            text_widget.insert(tk.END, pesan + "\n")
        text_widget.configure(state="disabled")
        text_widget.see(tk.END)

if __name__ == "__main__":
    root = tk.Tk()
    app = YamahaStyleToolkit(root)
    root.mainloop()