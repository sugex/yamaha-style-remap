import mido
import os

def baca_voice_style_yamaha(file_path):
    if not os.path.exists(file_path):
        print(f"File {file_path} tidak ditemukan.")
        return

    print(f"=== MEMBACA DATA VOICE & MSB/LSB ===")
    print(f"File: {os.path.basename(file_path)}\n")
    
    try:
        mid = mido.MidiFile(file_path)
        
        # Dictionary untuk menyimpan status MSB dan LSB per Channel (0-15)
        bank_status = {ch: {'msb': 0, 'lsb': 0} for ch in range(16)}
        voice_ditemukan = False

        for i, track in enumerate(mid.tracks):
            nama_trek = track.name if hasattr(track, 'name') else f"Trek {i}"
            
            for msg in track:
                # 1. Cek jika ada informasi teks nama Voice
                if msg.type in ['text', 'program_name']:
                    teks = msg.text.strip()
                    if teks and not teks.startswith(('SCh', 'MTr', 'CASM')):
                        print(f"[{nama_trek}] Info Teks Voice: {teks}")

                # Pastikan pesan MIDI memiliki atribut channel sebelum membaca MSB/LSB/PC
                if not hasattr(msg, 'channel'):
                    continue
                
                ch = msg.channel

                # 2. Tangkap nilai Bank Select MSB (Control Change 0)
                if msg.type == 'control_change' and msg.control == 0:
                    bank_status[ch]['msb'] = msg.value

                # 3. Tangkap nilai Bank Select LSB (Control Change 32)
                elif msg.type == 'control_change' and msg.control == 32:
                    bank_status[ch]['lsb'] = msg.value

                # 4. Tangkap Program Change (Menggunakan msg.program, bukan msg.value)
                elif msg.type == 'program_change':
                    msb = bank_status[ch]['msb']
                    lsb = bank_status[ch]['lsb']
                    pc = msg.program + 1  # Standard Yamaha menggunakan 1-128
                    
                    print(f"➔ {nama_trek} (Channel {ch + 1}):")
                    print(f"   • Bank MSB    : {msb}")
                    print(f"   • Bank LSB    : {lsb}")
                    print(f"   • Program No  : {pc}")
                    print(f"   • Format Bank : {msb}-{lsb}-{pc}")
                    print("-" * 45)
                    voice_ditemukan = True

        if not voice_ditemukan:
            print("Tidak ditemukan data Voice (Program Change) standar pada file ini.")

    except Exception as e:
        print(f"Gagal membaca file. Error: {e}")

# --- Cara Penggunaan ---
file_style = "tes1.sty" 

baca_voice_style_yamaha(file_style)