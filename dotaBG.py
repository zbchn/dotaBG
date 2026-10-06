import os
import sys
import time
import struct
import zlib
import shutil
import subprocess
import winreg

if getattr(sys, 'frozen', False):
    SCRIPT_DIR = os.path.dirname(sys.executable)
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

TEMPLATES_DIR = os.path.join(SCRIPT_DIR, "templates")

def get_ffmpeg():
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        bundled = os.path.join(sys._MEIPASS, "ffmpeg.exe")
        if os.path.exists(bundled):
            return bundled
    
    local = os.path.join(SCRIPT_DIR, "ffmpeg.exe")
    if os.path.exists(local):
        return local
        
    local_bin = os.path.join(SCRIPT_DIR, "bin", "ffmpeg.exe")
    if os.path.exists(local_bin):
        return local_bin

    if shutil.which("ffmpeg"):
        return "ffmpeg"

    return None

def build_vpk(file_dict, output_vpk_path):
    tree = {}
    for internal_path, data in file_dict.items():
        parts = internal_path.replace("\\", "/").split("/")
        full_name = parts[-1]
        directory = "/".join(parts[:-1]) if len(parts) > 1 else ""
        if "." in full_name:
            fname, ext = full_name.rsplit(".", 1)
        else:
            fname, ext = full_name, ""
        tree.setdefault(ext, {}).setdefault(directory, {})[fname] = data

    tree_bytes = bytearray()
    data_bytes = bytearray()
    curr_offset = 0

    for ext, dirs in tree.items():
        tree_bytes.extend(ext.encode("utf-8") + b"\x00")
        for directory, files in dirs.items():
            tree_bytes.extend(directory.encode("utf-8") + b"\x00")
            for fname, content in files.items():
                tree_bytes.extend(fname.encode("utf-8") + b"\x00")
                crc = zlib.crc32(content) & 0xFFFFFFFF
                preload_len = 0
                arch_idx = 0x7FFF
                meta = struct.pack("<IHHIIH", crc, preload_len, arch_idx, curr_offset, len(content), 0xFFFF)
                tree_bytes.extend(meta)
                data_bytes.extend(content)
                curr_offset += len(content)
            tree_bytes.append(0)
        tree_bytes.append(0)
    tree_bytes.append(0)

    header = struct.pack("<III", 0x55AA1234, 1, len(tree_bytes))
    os.makedirs(os.path.dirname(os.path.abspath(output_vpk_path)), exist_ok=True)
    with open(output_vpk_path, "wb") as f:
        f.write(header)
        f.write(tree_bytes)
        f.write(data_bytes)

def get_steam_path():
    for root_key, sub_key in [
        (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam")
    ]:
        try:
            key = winreg.OpenKey(root_key, sub_key)
            val, _ = winreg.QueryValueEx(key, "SteamPath" if root_key == winreg.HKEY_CURRENT_USER else "InstallPath")
            winreg.CloseKey(key)
            return os.path.normpath(val)
        except Exception:
            pass
    for p in [r"C:\Program Files (x86)\Steam", r"C:\Steam", r"D:\Steam"]:
        if os.path.exists(p):
            return p
    return None

def find_dota_russian_folder(steam_path):
    candidates = []
    if steam_path:
        candidates.append(os.path.join(steam_path, "steamapps"))
        vdf = os.path.join(steam_path, "steamapps", "libraryfolders.vdf")
        if os.path.exists(vdf):
            try:
                with open(vdf, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if '"path"' in line.lower():
                            parts = line.split('"')
                            if len(parts) >= 4:
                                candidates.append(os.path.join(os.path.normpath(parts[3]), "steamapps"))
            except Exception:
                pass

    for drive in ["C", "D", "E", "F", "G"]:
        candidates.append(os.path.join(f"{drive}:\\", "SteamLibrary", "steamapps"))
        candidates.append(os.path.join(f"{drive}:\\", "Games", "Steam", "steamapps"))

    for c in candidates:
        dota_dir = os.path.join(c, "common", "dota 2 beta", "game")
        if os.path.exists(dota_dir):
            target = os.path.join(dota_dir, "dota_russian")
            os.makedirs(target, exist_ok=True)
            return target
    return None

def close_processes():
    print("[*] Закрытие процессов Dota 2 и Steam для применения настроек...")
    subprocess.run(["taskkill", "/F", "/T", "/IM", "dota2.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["taskkill", "/F", "/T", "/IM", "steam.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)

def apply_steam_launch_options(steam_path):
    if not steam_path:
        return False
    user_dir = os.path.join(steam_path, "userdata")
    if not os.path.exists(user_dir):
        return False

    success = False
    required_flags = "-language russian -map_enable_background_maps 0"
    for uid in os.listdir(user_dir):
        cfg = os.path.join(user_dir, uid, "config", "localconfig.vdf")
        if not os.path.isfile(cfg):
            continue
        try:
            with open(cfg, "r", encoding="utf-8", errors="ignore") as f:
                data = f.read()

            if '"570"' in data:
                idx = data.find('"570"')
                b_open = data.find("{", idx)
                b_close = data.find("}", b_open)
                block = data[b_open:b_close]
                
                if '"LaunchOptions"' in block:
                    sub_i = block.find('"LaunchOptions"')
                    l_end = block.find("\n", sub_i)
                    full_line = block[sub_i:l_end]
                    parts = full_line.split('"')
                    cur_opt = parts[3] if len(parts) >= 4 else ""
                    
                    new_opts = cur_opt
                    if "-language russian" not in new_opts:
                        new_opts += " -language russian"
                    if "-map_enable_background_maps 0" not in new_opts:
                        new_opts += " -map_enable_background_maps 0"
                    
                    new_line = f'"LaunchOptions"\t\t"{new_opts.strip()}"'
                    data = data.replace(full_line, new_line, 1)
                else:
                    insert_str = f'\n\t\t\t\t"LaunchOptions"\t\t"{required_flags}"'
                    data = data[:b_open+1] + insert_str + data[b_open+1:]

                with open(cfg, "w", encoding="utf-8", errors="ignore") as f:
                    f.write(data)
                print(f"[+] Параметры запуска обновлены для профиля Steam ({uid}).")
                success = True
        except Exception as e:
            print(f"[-] Ошибка обновления конфига: {e}")
    return success

def restart_steam_and_launch_dota(steam_path):
    print("\n[*] Запуск Steam и Dota 2...")
    subprocess.run(["cmd", "/c", "start", "steam://run/570//-language%20russian%20-map_enable_background_maps%200"], shell=True)
    print("[+] Игра запускается!")

def convert_media_to_webm(ffmpeg_path, input_file, output_webm):
    print(f"[*] Конвертация '{os.path.basename(input_file)}' в WebM VP9 (растягивание на 1920x1080)...")
    ext = os.path.splitext(input_file)[1].lower()
    is_image = ext in [".png", ".jpg", ".jpeg", ".bmp", ".webp"]
    scale_filter = "scale=1920:1080"

    if is_image:
        cmd = [
            ffmpeg_path, "-y",
            "-loop", "1",
            "-i", input_file,
            "-c:v", "libvpx-vp9",
            "-t", "5",
            "-pix_fmt", "yuv420p",
            "-vf", scale_filter,
            "-b:v", "2M",
            "-an", output_webm
        ]
    else:
        cmd = [
            ffmpeg_path, "-y",
            "-i", input_file,
            "-c:v", "libvpx-vp9",
            "-pix_fmt", "yuv420p",
            "-vf", scale_filter,
            "-b:v", "0",
            "-crf", "28",
            "-r", "60",
            "-an", output_webm
        ]

    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        print(f"[-] Ошибка конвертации: {p.stderr.decode('utf-8', errors='ignore')}")
        return False
    return True

def collect_pak03_files(variant_choice, webm_bytes):
    if not os.path.exists(TEMPLATES_DIR):
        print(f"[-] Папка с шаблонами '{TEMPLATES_DIR}' не найдена!")
        print("    Убедитесь, что папка templates находится рядом со скриптом.")
        return None

    files = {}
    files["123/123.webm"] = webm_bytes

    common_dir = os.path.join(TEMPLATES_DIR, "common")
    if os.path.exists(common_dir):
        for root, _, fnames in os.walk(common_dir):
            for fn in fnames:
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, common_dir).replace("\\", "/")
                with open(full, "rb") as f:
                    files[rel] = f.read()

    if variant_choice in [2, 4]:
        home_path = os.path.join(TEMPLATES_DIR, "hide_carnival", "panorama", "layout", "dashboard_page_home.vxml_c")
        if os.path.exists(home_path):
            with open(home_path, "rb") as f:
                files["panorama/layout/dashboard_page_home.vxml_c"] = f.read()

    kv_folder = "show_kvortero" if variant_choice in [1, 2] else "hide_kvortero"
    kv_dir = os.path.join(TEMPLATES_DIR, kv_folder)
    if os.path.exists(kv_dir):
        for root, _, fnames in os.walk(kv_dir):
            for fn in fnames:
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, kv_dir).replace("\\", "/")
                with open(full, "rb") as f:
                    files[rel] = f.read()

    return files

def select_input_file():
    input_file = ""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes("-topmost", 1)
        root.update()
        input_file = filedialog.askopenfilename(
            title="Выберите фон (видео, гифку или изображение)",
            filetypes=[("Медиафайлы", "*.mp4 *.webm *.gif *.png *.jpg *.jpeg *.mkv *.avi"), ("Все файлы", "*.*")]
        )
        root.destroy()
    except Exception:
        input_file = ""

    if not input_file:
        print("\n[?] Окно выбора закрыто или не открылось.")
        print("    Перетащите файл в это окно консоли и нажмите Enter:")
        raw = input("    Файл: ").strip().strip('"').strip("'")
        input_file = raw

    return input_file

def main():
    print("=" * 65)
    print("                            dotaBG")
    print("                         def by zbchn")
    print("                      https://zoboch.in")
    print("=" * 65)

    src_pak02 = os.path.join(SCRIPT_DIR, "pak02_dir.vpk")
    if not os.path.exists(src_pak02):
        print(f"[!] Внимание: файл '{src_pak02}' не найден в папке со скриптом!")
        print("    Пожалуйста, положите pak02_dir.vpk рядом с программой.")
        input("\nНажмите Enter для выхода...")
        return

    print("[*] Поиск директории Dota 2...")
    steam_path = get_steam_path()
    dota_russian_dir = find_dota_russian_folder(steam_path)

    if not dota_russian_dir:
        print("[!] Не удалось автоматически обнаружить папку 'dota 2 beta/game/'.")
        raw = input("    Введите полный путь к папке dota_russian вручную: ").strip().strip('"')
        if os.path.exists(raw):
            dota_russian_dir = raw
        else:
            print("[-] Папка не найдена. Завершение работы.")
            input("\nНажмите Enter для выхода...")
            return
    print(f"[+] Папка мода: {dota_russian_dir}")

    input_file = select_input_file()
    if not input_file or not os.path.exists(input_file):
        print("[-] Файл не выбран или не существует. Отмена.")
        input("\nНажмите Enter для выхода...")
        return

    temp_webm = os.path.join(SCRIPT_DIR, "temp_123.webm")
    if input_file.lower().endswith(".webm"):
        print("[+] Файл уже в формате WebM. Конвертация не требуется!")
        shutil.copyfile(input_file, temp_webm)
    else:
        ffmpeg_bin = get_ffmpeg()
        if not ffmpeg_bin:
            print("[-] FFmpeg не найден! Положите ffmpeg.exe рядом с программой или используйте .webm.")
            input("\nНажмите Enter для выхода...")
            return
        ok = convert_media_to_webm(ffmpeg_bin, input_file, temp_webm)
        if not ok:
            input("\nНажмите Enter для выхода...")
            return

    with open(temp_webm, "rb") as f:
        webm_data = f.read()
    if os.path.exists(temp_webm):
        os.remove(temp_webm)

    print("\n" + "-" * 50)
    print("Выберите вариант отображения ивентов:")
    print("  1 — С ивентами (награды Квортеро + Dark Carnival)")
    print("  2 — Только с диковинками Квортеро (без Карнавала)")
    print("  3 — Только с Карнавалом (Dark Carnival, без Квортеро)")
    print("  4 — Без ивентов (чистый кастомный фон)")
    print("-" * 50)

    while True:
        c_str = input("Введите цифру (1-4): ").strip()
        if c_str in ["1", "2", "3", "4"]:
            variant = int(c_str)
            break
        print("Введите число от 1 до 4.")

    close_processes()

    print("\n[*] Сборка pak03_dir.vpk...")
    pak03_files = collect_pak03_files(variant, webm_data)
    if not pak03_files:
        input("\nНажмите Enter для выхода...")
        return

    target_pak03 = os.path.join(dota_russian_dir, "pak03_dir.vpk")
    build_vpk(pak03_files, target_pak03)
    print(f"[+] pak03_dir.vpk успешно собран и записан в dota_russian!")

    target_pak02 = os.path.join(dota_russian_dir, "pak02_dir.vpk")
    shutil.copyfile(src_pak02, target_pak02)
    print(f"[+] pak02_dir.vpk успешно скопирован.")

    apply_steam_launch_options(steam_path)

    restart_steam_and_launch_dota(steam_path)

    print("\n" + "=" * 65)
    print("  [ГОТОВО!] Фон установлен, Steam и Dota 2 перезапущены!")
    print(f"  Файлы записаны в: {dota_russian_dir}")
    print("=" * 65)
    input("\nНажмите Enter для завершения...")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print("\n" + "!" * 65)
        print("ПРОИЗОШЛА ОШИБКА:")
        traceback.print_exc()
        print("!" * 65)
        input("\nНажмите Enter для закрытия окна...")