#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Auto Buyer & Poster for VK Chat
--------------------------------
Этот скрипт автоматизирует процесс «скупки» предметов для игры Подземелья Колодца в ВКонтакте,
отправляет автопост с настраиваемым текстом и автоматически переводит золото тем,
кто прислал соответствующие предметы.

Рекомендации:
1. Установите все зависимости:
   pip install vk_api selenium colorama requests

2. Заполните переменные: токен, ссылка на профиль, ссылка на настройки в профиле и т.д.

3. Запустите скрипт и следите за логами в консоли.

Авторизация:
 - Скрипт использует longpoll от vk_api для получения входящих сообщений из чата.

GitHub: https://github.com/WellDungeonBot/WellDungeon-AutoBuyer-WDB
Лицензия: MIT
"""

import json
import os
import re
import sys
import time
import traceback
from datetime import datetime, timedelta

import vk_api
from vk_api import utils
from vk_api.longpoll import VkEventType, VkLongPoll
from colorama import Style, Fore

from selenium import webdriver
from selenium.webdriver.common.by import By

# ========== ПУТИ К ФАЙЛАМ ==========
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATETIME_PATH = os.path.join(BASE_DIR, 'last-datetime.txt')
PRICE_LIST_JSON = os.path.join(BASE_DIR, 'price_list.json')

# ========== НАСТРОЙКИ ПРОФИЛЯ И ЧАТА ==========
PROFILE_LINK = 'LINK_1'       # Ссылка на страницу персонажа (VIP3)
SETTINGS_LINK = 'LINK_2'      # Ссылка на страницу включения/выключения приёма передач
TOKEN = 'YOUR_VK_TOKEN'       # Токен аккаунта ВК
CHAT_ID = 2000000001          # ID чата, в котором ведётся скупка
SERVICE_CHAT_ID = -227249427  # ID служебного чата (в данном случае чат с нашим сообществом https://vk.com/wdb_fun)
AUTOPOST_TEXT = "Автоскупом покупаю:" # Отображаемая шапка текста для автопоста
GOLD_LIMIT = 50000 # Количество золота, которое является порогом для включения/отключения приёма передач

# ========== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ (НЕ ТРОГАТЬ) ==========
op = webdriver.ChromeOptions()
op.add_argument('headless')
op.add_argument('no-sandbox')
driver = webdriver.Chrome(options=op)

skup_flag = True               # Флаг включённой/выключенной скупки
additional_text = ""           # Дополнительный текст в автопосте
price_list = {}                # Словарь {предмет: цена}
FIRST_NAME = ""
LAST_NAME = ""
ACCOUNT_ID = 0
pause_flag = False

# ========== ПАЛИТРА ДЛЯ ЛОГОВ (colorama) ==========
ly = Fore.LIGHTYELLOW_EX
lg = Fore.LIGHTGREEN_EX
lr = Fore.LIGHTRED_EX
lm = Fore.LIGHTMAGENTA_EX
lc = Fore.LIGHTCYAN_EX
g = Fore.GREEN
d = Style.RESET_ALL

# ========== СООТВЕТСТВИЕ ПРЕДМЕТ -> ЭМОДЖИ ==========
emoji = {
    "грязный удар": "📕", "слабое исцеление": "📕", "удар вампира": "📕", "мощный удар": "📕", "сила теней": "📕",
    "расправа": "📕", "слепота": "📕", "рассечение": "📕", "берсеркер": "📕", "таран": "📕", "проклятие тьмы": "📕",
    "огонек надежды": "📕", "целебный огонь": "📕", "кровотечение": "📕", "заражение": "📕", "раскол": "📕",
    "инициативность": "📘", "быстрое восстановление": "📘", "мародер": "📘", "внимательность": "📘",
    "исследователь": "📘", "ведьмак": "📘", "собиратель": "📘", "запасливость": "📘", "охотник за головами": "📘",
    "подвижность": "📘", "упорность": "📘", "регенерация": "📘", "расчетливость": "📘", "ошеломление": "📘",
    "рыбак": "📘", "неуязвимый": "📘", "колющий удар": "📘", "бесстрашие": "📘", "режущий удар": "📘",
    "феникс": "📘", "непоколебимый": "📘", "суеверность": "📘", "гладиатор": "📘", "воздаяние": "📘",
    "ученик": "📘", "прочность": "📘", "расторопность": "📘", "устрашение": "📘", "контратака": "📘",
    "дробящий удар": "📘", "защитная стойка": "📘", "стойка сосредоточения": "📘", "водохлеб": "📘",
    "картограф": "📘", "браконьер": "📘", "парирование": "📘", "ловкость рук": "📘", "незаметность": "📘",
    "атлетика": "📘", "устойчивость": "📘", "угроза": "📘"
}

# ============================================================================
#                        ФУНКЦИИ УПРАВЛЕНИЯ СКУПКОЙ
# ============================================================================

def skup_off():
    """
    Выключает приём передач на странице настроек.
    """
    global skup_flag
    driver.get(SETTINGS_LINK)
    driver.execute_script("window.run_program(this, '51173l3l06edf74935f97a43', 0, 0);")
    skup_flag = False


def skup_on():
    """
    Включает приём передач на странице настроек.
    """
    global skup_flag
    driver.get(SETTINGS_LINK)
    driver.execute_script("window.run_program(this, '51173l4l86ac1c1d73744501', 0, 0);")
    skup_flag = True


def change_status():
    """
    Проверяет текущее количество золота в профиле.
    Если золота >= GOLD_LIMIT и скупка выключена -> включает скупку.
    Если золота < GOLD_LIMIT и скупка включена -> выключает скупку.
    """
    try:
        driver.get(PROFILE_LINK)
        gold_str = driver.find_element(By.ID, "r_13322").find_element(By.TAG_NAME, "span").text.strip()
        gold = int(gold_str)
        print(f"[INFO] My gold: {gold}")

        if gold >= GOLD_LIMIT and not skup_flag: skup_on()
        elif gold < GOLD_LIMIT and skup_flag: skup_off()
    except Exception:
        print(traceback.format_exc())

# ============================================================================
#             КЛАСС ДЛЯ РАСШИРЕННОЙ РАБОТЫ С LONGPOLL
# ============================================================================

class MyVkLongPoll(VkLongPoll):
    """
    Переопределение стандартного VkLongPoll с исправлением множества ошибок.
    """
    def update_longpoll_server(self, update_ts=True):
        values = {'lp_version': '3', 'need_pts': self.pts}
        if self.group_id:
            values['group_id'] = self.group_id
        response = self.vk.method('messages.getLongPollServer', values)
        self.key = response['key']
        self.server = response['server']
        self.url = f"https://{self.server}"
        if update_ts:
            self.ts = response.get('ts')
            if self.pts:
                self.pts = response.get('pts')

    def check(self):
        values = {
            'act': 'a_check',
            'key': self.key,
            'ts': self.ts,
            'wait': self.wait,
            'mode': self.mode,
            'version': 3
        }
        response = self.session.get(self.url, params=values, timeout=self.wait + 10).json()

        if 'failed' not in response:
            self.ts = response.get('ts')
            if self.pts:
                self.pts = response.get('pts')
            events = []
            for raw_event in response['updates']:
                try:
                    event = self._parse_event(raw_event)
                    events.append(event)
                except Exception as e:
                    print(f"[ERROR] Ошибка при обработке события: {e}")
                    continue
            if self.preload_messages:
                self.preload_message_events_data(events)
            return events

        elif response['failed'] == 1:
            self.ts = response.get('ts')
        elif response['failed'] in (2, 3):
            self.update_longpoll_server(update_ts=(response['failed'] == 3))

        print('[WARNING] check() вернул пустой список событий!')
        return []

    def listen(self):
        while True:
            try:
                while True: yield from self.check()
            except Exception as e:
                print(f"[ERROR] В longpoll произошла ошибка типа {type(e).__name__}:")
                print(traceback.format_exc())
                print(f"[ERROR] Время ошибки: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# ============================================================================
#         ФУНКЦИИ ДЛЯ РАБОТЫ С JSON ПРАЙС-ЛИСТОМ
# ============================================================================

def load_price_list():
    """
    Загружает прайс-лист из файла JSON и обновляет глобальный словарь price_list.
    Если файл не существует или повреждён, возвращает пустой словарь.
    """
    global price_list
    try:
        with open(PRICE_LIST_JSON, 'r', encoding='utf-8') as f:
            price_list = json.load(f)
            price_list = {key.lower(): value for key, value in price_list.items()}
    except (FileNotFoundError, json.JSONDecodeError): price_list = {}
    print(f"[INFO] Ваш прайс-лист: {price_list}")
    return price_list

def save_price_list():
    """
    Сохраняет глобальный словарь price_list в файл JSON.
    """
    with open(PRICE_LIST_JSON, 'w', encoding='utf-8') as f:
        json.dump(price_list, f, ensure_ascii=False, indent=4)

# ============================================================================
#                           РАБОТА С ДАТАМИ
# ============================================================================

def save_last_post_time(post_time: datetime):
    """
    Сохраняет дату/время последнего автопоста в файл DATETIME_PATH в ISO-формате.
    """
    with open(DATETIME_PATH, 'w', encoding='utf-8') as f:
        f.write(post_time.isoformat())

def load_last_post_time() -> datetime:
    """
    Считывает дату/время последнего автопоста из DATETIME_PATH, возвращает datetime.
    """
    try:
        with open(DATETIME_PATH, 'r', encoding='utf-8') as f: dt_str = f.read().strip()
        return datetime.fromisoformat(dt_str)
    except (FileNotFoundError, ValueError):
        print(f"{lr}[ERROR] Ошибка чтения времени последнего автопоста{d}")
        current_time = datetime.now()
        save_last_post_time(current_time)
        return current_time

# ============================================================================
#                 ФУНКЦИЯ ФОРМИРОВАНИЯ АВТОПОСТА
# ============================================================================

def get_emoji(item_name):
    """
    Возвращает emoji для предмета, если оно есть в словаре emoji.
    """
    return emoji.get(item_name.lower(), "")

def now_autopost_text():
    """
    Формирует текущий текст автопоста на основе актуального прайс-листа.
    """
    load_price_list()  # Обновляем данные из файла
    result = AUTOPOST_TEXT
    categories = ["📕", "📘", ""]
    for cat in categories:
        for item, cost in price_list.items():
            if get_emoji(item) == cat:
                item_text = item.capitalize()
                result += f"\n{cat}{item_text} - {cost}🌕"
    if additional_text: result += f"\n{additional_text}"
    return result

def send_autopost(vk_session):
    """
    Отправляет сформированный текст автопоста в нужный чат (CHAT_ID).
    """
    vk_session.method('messages.send', {
        'random_id': 0,
        'peer_id': CHAT_ID,
        'message': now_autopost_text(),
    })

# ============================================================================
#                  ФУНКЦИИ ДЛЯ ОБРАБОТКИ СООБЩЕНИЙ
# ============================================================================

def authorize(vk_session):
    """
    Авторизует скрипт в ВК по токену, выводит имя/фамилию/ID аккаунта.
    """
    info_account = vk_session.method('account.getProfileInfo', {})
    first_name = info_account["first_name"]
    last_name = info_account["last_name"]
    account_id = info_account["id"]
    print(f"[INFO] Аккаунт {lm}{first_name} {last_name} ({account_id}){lg} успешно авторизован!{d}")
    return first_name, last_name, account_id

def get_last_mid_from_uid(vk_session, uid):
    """
    Возвращает ID последнего сообщения пользователя с указанным user_id (uid) из чата CHAT_ID.
    """
    history = vk_session.method('messages.getHistory', {
        'count': 200,
        'peer_id': CHAT_ID,
    })
    for msg_tuple in history.items():
        for msg_1 in msg_tuple:
            if isinstance(msg_1, list):
                for msg_2 in msg_1:
                    if msg_2.get("from_id") == uid:
                        return msg_2.get("id")
    return None

def send_money(vk_session, uid, cost):
    """
    Отправляет сообщение "Передать XXX золота" в чат, реплаем на последнее сообщение пользователя uid.
    """
    msg = f"Передать {cost} золота"
    vk_session.method('messages.send', {
        'peer_id': CHAT_ID,
        'message': msg,
        'reply_to': get_last_mid_from_uid(vk_session, uid),
        'random_id': 0
    })
    print(f"{lg}[INFO] Отправлены деньги ({datetime.now().strftime('%H:%M:%S')}): \n\t{g}{msg}{d}\n")

def message_processor(vk_session, event, account_id, first_name):
    """
    Обрабатывает полученное сообщение на предмет нужных ключевых слов.
    Если предмет найден в price_list, вызывается send_money().
    """
    msg = event.text.lower()
    mention_pattern = f"[id{account_id}|{first_name.lower()}]"
    if mention_pattern in msg:
        uid_start_idx = msg.rfind("id") + 2
        uid_end_idx = msg.rfind("|")
        uid = int(msg[uid_start_idx:uid_end_idx])
        for item, cost in price_list.items():
            if "получено:" in msg and "от игрока" in msg and item.lower() in msg:
                print(f"{lg}[INFO] Получен предмет ({datetime.now().strftime('%H:%M:%S')}): \n\t{g}{msg}{d}\n")
                item_index = msg.find(item)
                quantity = 1
                prefix = msg[item_index - 3:item_index]
                match_digits = re.search(r'(\d+)\*', prefix)
                if match_digits:
                    quantity = int(match_digits.group(1))
                total_cost = str(quantity * cost)
                send_money(vk_session, uid, total_cost)

def send_answer(vk_session, event, answer):
    """
    Отправляет ответное сообщение в реплай на исходное (по event.message_id).
    """
    vk_session.method('messages.send', {
        'random_id': 0,
        'peer_id': event.peer_id,
        'message': answer,
        'reply_to': event.message_id
    })

# ============================================================================
#         ФУНКЦИЯ ОБРАБОТКИ СООБЩЕНИЙ ИВЕНТА LONGPOLL
# ============================================================================

def await_event(vk_session, lp):
    """
    Обрабатывает входящие сообщения, переключает статус скупки,
    делает автопост при необходимости, добавляет/удаляет/изменяет предметы в прайс-листе.
    """
    global pause_flag, additional_text, AUTOPOST_TEXT
    for event in lp.listen():
        if event.type == VkEventType.MESSAGE_NEW:
            if event.peer_id == CHAT_ID:
                event_time = datetime.now()
                if (event_time - load_last_post_time()) > timedelta(minutes=180) and not pause_flag:
                    change_status()
                    save_last_post_time(event_time)
                    send_autopost(vk_session)
                if "получено:" in event.text.lower() \
                   and "от игрока" in event.text.lower() \
                   and event.user_id == -183040898:
                    message_processor(vk_session, event, ACCOUNT_ID, FIRST_NAME)
            elif event.peer_id == SERVICE_CHAT_ID and event.from_me:
                command_text = event.text.lower().strip()
                if "/скуп+" in command_text:
                    item_str = re.sub(r'/скуп\+', '', command_text, flags=re.IGNORECASE).strip()
                    if re.match(r'^[А-Яа-яёЁ\s]+:\s*\d+$', item_str):
                        try:
                            name, cost_str = item_str.split(':', 1)
                            name = name.strip().lower()
                            cost = int(cost_str.strip())
                            load_price_list()  # Обновляем текущий список
                            price_list[name] = cost
                            save_price_list()
                            send_answer(vk_session, event, now_autopost_text())
                        except Exception as e: send_answer(vk_session, event, f"Ошибка при добавлении: {e}")
                    else: send_answer(vk_session, event, "Ошибка: введённый предмет не соответствует шаблону.")
                elif "/скуп-" in command_text:
                    item_str = re.sub(r'/скуп-', '', command_text, flags=re.IGNORECASE).strip()
                    load_price_list()  # Обновляем текущий список
                    if item_str in price_list:
                        del price_list[item_str]
                        save_price_list()
                        send_answer(vk_session, event, now_autopost_text())
                    else:
                        send_answer(vk_session, event, "Ошибка: предмет не соответствует шаблону или отсутствует в прайс-листе.")
                elif "/скуп=" in command_text:
                    additional_text = re.sub(r'/скуп=', '', event.text.strip(), flags=re.IGNORECASE).strip()
                    send_answer(vk_session, event, now_autopost_text())
                elif "/скуп" == command_text:
                    send_answer(vk_session, event, f"Текущий текст автопоста:\n{now_autopost_text()}")
                elif "/скуптекст" in command_text:
                    AUTOPOST_TEXT = re.sub(r'/скуптекст', '', event.text.strip(), flags=re.IGNORECASE).strip()
                    send_answer(vk_session, event, now_autopost_text())
                elif "скуп, пауза" in command_text:
                    if pause_flag: send_answer(vk_session, event, "Автопост уже в состоянии паузы!")
                    else:
                        pause_flag = True
                        send_answer(vk_session, event, "Автопост установлен на паузу!")
                elif "скуп, пуск" in command_text:
                    if not pause_flag: send_answer(vk_session, event, "Автопост уже запущен!")
                    else:
                        pause_flag = False
                        send_answer(vk_session, event, "Автопост запущен!!")
                elif "скуп, выключись" in command_text:
                    print(f"\n{lr}[INFO] Отключение бота по команде пользователя!{d}")
                    send_answer(vk_session, event, "Выключаюсь!")
                    sys.exit()

def process():
    """
    Основной цикл «прослушки» событий.
    """
    while True:
        try: await_event(vk, longpoll)
        except Exception as err:
            err_str = str(err).replace('\n', '\n\t')
            print(f"{lr}[ERROR] Произошла ошибка ({datetime.now().strftime('%H:%M:%S')}):\n\t{err_str}")
            print(traceback.format_exc())
            time.sleep(1)
            continue


# ============================================================================
#                                   MAIN
# ============================================================================

if __name__ == '__main__':
    print(r"""
                                              
    ▀████▀     █     ▀███▀███▀▀▀██▄ ▀███▀▀▀██▄
      ▀██     ▄██     ▄█   ██    ▀██▄ ██    ██
       ██▄   ▄███▄   ▄█    ██     ▀██ ██    ██
        ██▄  █▀ ██▄  █▀    ██      ██ ██▀▀▀█▄▄
        ▀██ █▀  ▀██ █▀     ██     ▄██ ██    ▀█
         ▄██▄    ▄██▄      ██    ▄██▀ ██    ▄█
          ██      ██     ▄████████▀ ▄████████                 
                                          
    Автоматический скупщик предметов в чате ВКонтакте для Подземелий Колодца
    """)

    print(f"[INFO] Последняя дата поста (из файла): {load_last_post_time()}")

    try: load_price_list()
    except Exception as e:
        print(f"{lr}[ERROR] Ошибка чтения прайс-листа:\n\t{e}{d}")
        sys.exit(1)

    vk = vk_api.VkApi(token=TOKEN)
    longpoll = MyVkLongPoll(vk)
    FIRST_NAME, LAST_NAME, ACCOUNT_ID = authorize(vk)

    process()
