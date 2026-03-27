# Kling Video-to-Audio via WaveSpeed API — Дорожная карта

## Цель
Кастомная нода ComfyUI, которая принимает видео и генерирует видео с аудио,
используя WaveSpeed API (endpoint: kwaivgi/kling-video-to-audio).

## Архитектура
- Вход: VIDEO, sound_effect_prompt (str), bgm_prompt (str), asmr_mode (bool), api_key (str)
- API: POST https://api.wavespeed.ai/api/v3/kwaivgi/kling-video-to-audio
- Поллинг: GET https://api.wavespeed.ai/api/v3/predictions/{id}/result
- Выход: VIDEO (mp4 с аудио)

## Файловая структура
```
ComfyUI_kling_video_2_audio/
├── __init__.py          # регистрация нод
├── nodes.py             # основная нода
├── api_client.py        # HTTP-клиент (upload, submit, poll)
├── ROADMAP.md           # этот файл
└── README.md            # документация для пользователя
```

## Этапы

### [x] Этап 0: Создать папку проекта и ROADMAP.md
- Создана папка ComfyUI_kling_video_2_audio
- Создан ROADMAP.md

### [x] Этап 1: api_client.py — HTTP-клиент WaveSpeed
- upload_video() — загрузить локальный файл, получить URL
- submit_video2audio() — отправить задачу на генерацию
- poll_result() — поллить до completed/failed
- download_result() — скачать результат во временный файл

### [x] Этап 2: nodes.py — определение ноды ComfyUI
- Класс KlingVideo2Audio
- INPUT_TYPES: video (путь), prompts, asmr_mode, api_key
- RETURN_TYPES: VIDEO
- FUNCTION: execute — оркестрирует api_client

### [x] Этап 3: __init__.py — регистрация
- NODE_CLASS_MAPPINGS
- NODE_DISPLAY_NAME_MAPPINGS

### [x] Этап 4: README.md — инструкция
- Установка, настройка API key, использование

### [x] Этап 5a: VHS-совместимый превью
- Изучен паттерн VHS VideoCombine: {"ui": {"gifs": [preview]}}
- Обновлён nodes.py: результат сохраняется в output/ через folder_paths
- Возврат включает preview dict для отображения видео в ноде
- STRING output (video_path) сохраняется для цепочки с другими нодами

### [x] Этап 5b: Upload-нода с dropdown + кнопка Upload
- Изучен паттерн VHS LoadVideoUpload: folder_paths.get_input_directory()
- Создана KlingVideo2Audio (Upload) — dropdown видеофайлов + Upload кнопка
- Переименована старая в KlingVideo2AudioPath (Path) — для цепочки нод
- KlingVideo2AudioURL (URL) — без изменений
- Рефакторинг: вынесены _resolve_api_key, _save_to_output, _run_v2a
- IS_CHANGED + VALIDATE_INPUTS по паттерну VHS

### [ ] Этап 6: Тестирование (пользователь)
- Перезапустить ComfyUI
- Проверить три ноды: Upload, URL, Path
- Проверить что кнопка Upload появилась
- Прогнать с реальным видео и API-ключом
