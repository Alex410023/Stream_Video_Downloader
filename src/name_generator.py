import re


def clean_name(slug):
    """Превращает slug (например, stranger-things-2016) в красивую строку."""
    # Заменяем тире и подчеркивания на пробелы
    name = slug.replace("-", " ").replace("_", " ")
    # Делаем каждое слово с большой буквы
    name = " ".join([word.capitalize() for word in name.split()])
    return name


def generate_movie_name(url):
    """Извлекает и генерирует осмысленное имя фильма из URL."""
    if not url:
        return ""

    # Ищем имя папки после /films/
    match = re.search(r'/films/([^/]+)', url)
    if match:
        return clean_name(match.group(1))

    # Ищем имя папки после /series/
    match = re.search(r'/series/([^/]+)', url)
    if match:
        return clean_name(match.group(1))

    # Резервный вариант: берем последний сегмент пути перед файлом
    parts = [p for p in url.split("/") if p]
    if len(parts) > 2:
        last_idx = -1
        while last_idx >= -len(parts):
            segment = parts[last_idx]
            # Игнорируем имена файлов и слишком короткие папки
            if "." not in segment and len(segment) > 3:
                return clean_name(segment)
            last_idx -= 1
    return ""


def generate_series_name(url, season=None, episode=None):
    """Генерирует имя серии сериала в формате Название_S01E05."""
    base_name = generate_movie_name(url)
    if not base_name:
        return ""

    # Форматируем сезон и серию
    s_str = f"S{int(season):02d}" if season is not None else ""
    e_str = f"E{int(episode):02d}" if episode is not None else ""

    if s_str and e_str:
        return f"{base_name}_{s_str}{e_str}"
    elif s_str:
        return f"{base_name}_{s_str}"
    elif e_str:
        return f"{base_name}_{e_str}"
    return base_name