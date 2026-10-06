import os
import sys
import struct

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(SCRIPT_DIR, "templates")

def parse_and_extract_vpk(vpk_path):
    """
    Распаковывает VPK (v1 и v2) прямо в память и возвращает
    словарь {относительный_путь: бинарные_данные}.
    """
    extracted = {}
    with open(vpk_path, "rb") as f:
        header = f.read(12)
        if len(header) < 12:
            return extracted
        
        signature, version, tree_size = struct.unpack("<III", header)
        if signature != 0x55AA1234:
            print(f"[-] Файл {os.path.basename(vpk_path)} не является корректным VPK!")
            return extracted

        if version == 2:
            f.read(16)  # Пропускаем расширенный заголовок VPK v2

        tree_bytes = f.read(tree_size)
        offset = 0

        def read_null_string(data, off):
            end = data.find(b"\x00", off)
            if end == -1:
                return "", len(data)
            return data[off:end].decode("utf-8", errors="ignore"), end + 1

        entries = []
        while offset < len(tree_bytes):
            ext, offset = read_null_string(tree_bytes, offset)
            if not ext:
                break
            while offset < len(tree_bytes):
                directory, offset = read_null_string(tree_bytes, offset)
                if not directory:
                    break
                while offset < len(tree_bytes):
                    filename, offset = read_null_string(tree_bytes, offset)
                    if not filename:
                        break
                    
                    data_entry = tree_bytes[offset:offset + 18]
                    offset += 18
                    _, preload_bytes, _, entry_offset, entry_length, _ = struct.unpack("<IHHIIH", data_entry)
                    
                    full_name = f"{directory}/{filename}.{ext}" if directory else f"{filename}.{ext}"
                    preload_data = b""
                    if preload_bytes > 0:
                        preload_data = tree_bytes[offset:offset + preload_bytes]
                        offset += preload_bytes
                    
                    entries.append((full_name, preload_data, entry_offset, entry_length))

        data_start_offset = 12 + (16 if version == 2 else 0) + tree_size

        for full_name, preload_data, entry_offset, entry_length in entries:
            f.seek(data_start_offset + entry_offset)
            file_bytes = preload_data + f.read(entry_length)
            extracted[full_name.replace("\\", "/")] = file_bytes

    return extracted


def save_file(target_root, rel_path, data):
    full_path = os.path.join(target_root, rel_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "wb") as f:
        f.write(data)
    print(f"  [+] Записан: {os.path.relpath(full_path, SCRIPT_DIR)}")


def find_file_by_patterns(folder, patterns):
    """Ищет файл в папке по частичным совпадениям названия."""
    for fname in os.listdir(folder):
        f_lower = fname.lower()
        if f_lower.endswith(".vpk") and all(p.lower() in f_lower for p in patterns):
            return os.path.join(folder, fname)
    return None


def main():
    print("=" * 65)
    print("    АВТОМАТИЧЕСКАЯ РАСПАКОВКА И СОРТИРОВКА ШАБЛОНОВ VPK")
    print("=" * 65)

    # 1. Поиск исходных VPK файлов в текущей папке
    bg_vpk = find_file_by_patterns(SCRIPT_DIR, ["background"])
    carnaval_vpk = find_file_by_patterns(SCRIPT_DIR, ["carnaval"]) or find_file_by_patterns(SCRIPT_DIR, ["carnival"])
    kvortero_vpk = find_file_by_patterns(SCRIPT_DIR, ["kvortero"])
    all_ivents_vpk = find_file_by_patterns(SCRIPT_DIR, ["all", "ivents"]) or find_file_by_patterns(SCRIPT_DIR, ["all", "events"])

    if not bg_vpk and not all_ivents_vpk:
        print("[-] Не найдены исходные .vpk файлы в папке со скриптом.")
        print("Положите файлы ('only background.vpk', 'all ivents.vpk' и др.) рядом со скриптом.")
        input("\nНажмите Enter для выхода...")
        sys.exit(1)

    # Папки назначения
    dir_common = os.path.join(TEMPLATES_DIR, "common")
    dir_hide_carnival = os.path.join(TEMPLATES_DIR, "hide_carnival")
    dir_hide_kvortero = os.path.join(TEMPLATES_DIR, "hide_kvortero")
    dir_show_kvortero = os.path.join(TEMPLATES_DIR, "show_kvortero")

    # 2. Извлечение базовых общих файлов (из only background или любого другого)
    base_source = bg_vpk or all_ivents_vpk
    print(f"\n[*] Извлечение общих файлов из '{os.path.basename(base_source)}'...")
    base_data = parse_and_extract_vpk(base_source)

    common_files = [
        "panorama/layout/dashboard_background_manager.vxml_c",
        "panorama/layout/hero_loadout_background_images.vxml_c",
        "panorama/styles/dashboard_background_manager.vcss_c",
        "panorama/styles/hero_loadout_background_images.vcss_c"
    ]
    for rel_p in common_files:
        if rel_p in base_data:
            save_file(dir_common, rel_p, base_data[rel_p])

    # 3. Извлечение заглушки скрытия Карнавала (dashboard_page_home.vxml_c)
    # Этот файл присутствует в 'only background.vpk' и 'only kvortero.vpk'
    carnival_stub_source = bg_vpk or kvortero_vpk
    if carnival_stub_source:
        print(f"\n[*] Извлечение заглушки скрытия Карнавала из '{os.path.basename(carnival_stub_source)}'...")
        c_data = parse_and_extract_vpk(carnival_stub_source)
        if "panorama/layout/dashboard_page_home.vxml_c" in c_data:
            save_file(dir_hide_carnival, "panorama/layout/dashboard_page_home.vxml_c", c_data["panorama/layout/dashboard_page_home.vxml_c"])

    # 4. Извлечение заглушки скрытия Квортеро (без наград)
    # Присутствует в 'only background.vpk' и 'only dark carnaval.vpk'
    hide_kv_source = bg_vpk or carnaval_vpk
    if hide_kv_source:
        print(f"\n[*] Извлечение файлов скрытия Квортеро из '{os.path.basename(hide_kv_source)}'...")
        h_data = parse_and_extract_vpk(hide_kv_source)
        for rel_p in [
            "panorama/layout/dashboard_background_last_match.vxml_c",
            "panorama/styles/dashboard_background_last_match.vcss_c"
        ]:
            if rel_p in h_data:
                save_file(dir_hide_kvortero, rel_p, h_data[rel_p])

    # 5. Извлечение полных файлов наград Квортеро
    # Присутствует в 'all ivents.vpk' и 'only kvortero.vpk'
    show_kv_source = all_ivents_vpk or kvortero_vpk
    if show_kv_source:
        print(f"\n[*] Извлечение файлов показа наград Квортеро из '{os.path.basename(show_kv_source)}'...")
        s_data = parse_and_extract_vpk(show_kv_source)
        for rel_p in [
            "panorama/layout/dashboard_background_last_match.vxml_c",
            "panorama/styles/dashboard_background_last_match.vcss_c"
        ]:
            if rel_p in s_data:
                save_file(dir_show_kvortero, rel_p, s_data[rel_p])

    print("\n" + "=" * 65)
    print("[ГОТОВО!] Все файлы успешно распакованы и разложены по папкам.")
    print("Теперь можно запускать основной скрипт dotaBG.py!")
    print("=" * 65)
    input("\nНажмите Enter для завершения...")


if __name__ == "__main__":
    main()