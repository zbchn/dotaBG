import os
import sys
import time
import subprocess
import winreg

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
            return target
    return None

def close_processes():
    print("[*] Закрытие процессов Dota 2 и Steam...")
    subprocess.run(["taskkill", "/F", "/T", "/IM", "dota2.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["taskkill", "/F", "/T", "/IM", "steam.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)

def remove_files(dota_russian_dir):
    files_to_remove = ["pak02_dir.vpk", "pak03_dir.vpk"]
    for fname in files_to_remove:
        target_file = os.path.join(dota_russian_dir, fname)
        if os.path.exists(target_file):
            try:
                os.remove(target_file)
                print(f"[+] Удален: {fname}")
            except Exception as e:
                print(f"[-] Не удалось удалить {fname}: {e}")
        else:
            print(f"[-] Файл {fname} не найден в папке.")

def restart_steam_and_launch_dota(steam_path):
    if not steam_path:
        return
    steam_exe = os.path.join(steam_path, "steam.exe")
    if os.path.exists(steam_exe):
        print("\n[*] Запуск Steam и стандартной Dota 2...")
        subprocess.Popen([steam_exe, "-applaunch", "570"])
        print("[+] Команда на запуск игры отправлена!")

def main():
    print("=" * 65)
    print("                           resetBG")
    print("                         dev by zbchn")
    print("                      https://zoboch.in")
    print("=" * 65)

    steam_path = get_steam_path()
    dota_russian_dir = find_dota_russian_folder(steam_path)

    if not dota_russian_dir or not os.path.exists(dota_russian_dir):
        print("[!] Не удалось автоматически найти папку dota_russian.")
        raw = input("    Введите полный путь к папке dota_russian вручную: ").strip().strip('"')
        if os.path.exists(raw):
            dota_russian_dir = raw
        else:
            print("[-] Папка не найдена. Завершение работы.")
            input("\nНажмите Enter для выхода...")
            return

    print(f"[*] Папка мода найдена: {dota_russian_dir}")

    close_processes()
    remove_files(dota_russian_dir)
    restart_steam_and_launch_dota(steam_path)

    print("\n" + "=" * 65)
    print("  [ГОТОВО!] Кастомные файлы удалены, Dota 2 запущена в исходном виде.")
    print("=" * 65)
    input("\nНажмите Enter для завершения...")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        traceback.print_exc()
        input("\nНажмите Enter для закрытия окна...")