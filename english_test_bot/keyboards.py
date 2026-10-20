from aiogram.types import (InlineKeyboardButton as IB, InlineKeyboardMarkup,
                           KeyboardButton, ReplyKeyboardMarkup)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

import config

PAGE = 10


# ---------- Foydalanuvchi ----------
def main_menu(is_admin=False):
    b = ReplyKeyboardBuilder()
    for t in ["📝 Test topshirish", "📚 Kun so'zi", "📊 Natijalarim",
              "🏆 Reyting", "👤 Profil", "ℹ️ Yordam"]:
        b.button(text=t)
    if is_admin:
        b.button(text="🛠 Admin panel")
    b.adjust(2)
    return b.as_markup(resize_keyboard=True)


PHONE_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📱 Raqamni yuborish", request_contact=True)]],
    resize_keyboard=True, one_time_keyboard=True,
)


def sub_kb():
    rows = []
    if config.CHANNEL_URL:
        rows.append([IB(text="📢 Kanalga o'tish", url=config.CHANNEL_URL)])
    rows.append([IB(text="✅ Tekshirish", callback_data="chk_sub")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def start_test(tid):
    b = InlineKeyboardBuilder()
    b.button(text="▶️ Boshlash", callback_data=f"go:{tid}")
    b.button(text="⬅️ Boshqa kod", callback_data="tests:code")
    b.adjust(1)
    return b.as_markup()


def question_kb(idx):
    b = InlineKeyboardBuilder()
    for i, l in enumerate("ABCD"):
        b.button(text=l, callback_data=f"ans:{idx}:{i}")
    b.button(text="🛑 To'xtatish", callback_data="stop")
    b.adjust(4, 1)
    return b.as_markup()


def after_test():
    b = InlineKeyboardBuilder()
    b.button(text="📝 Boshqa test", callback_data="tests:code")
    return b.as_markup()


def word_kb():
    b = InlineKeyboardBuilder()
    b.button(text="🔄 Yana so'z", callback_data="word:next")
    return b.as_markup()


# ---------- Admin ----------
def admin_menu():
    b = InlineKeyboardBuilder()
    items = [
        ("➕ Yangi test", "adm:newtest"), ("📚 Testlar", "adm:tests"),
        ("👥 Foydalanuvchilar", "adm:users:0"), ("🚫 Bloklanganlar", "adm:blocked:0"),
        ("📊 Natijalar", "adm:results:0"), ("🏆 Reyting", "adm:top"),
        ("📥 Excel: foydalanuvchilar", "adm:xl_users"), ("📥 Excel: natijalar", "adm:xl_results"),
        ("🔍 Qidirish", "adm:search"), ("📈 Statistika", "adm:stats"),
        ("🔤 Lug'at so'zlari", "adm:words"), ("📢 Xabar yuborish", "adm:bc"),
    ]
    for t, c in items:
        b.button(text=t, callback_data=c)
    b.adjust(2)
    return b.as_markup()


def back_menu():
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ Admin panel", callback_data="adm:menu")
    return b.as_markup()


def users_list(rows, page, total, prefix):
    b = InlineKeyboardBuilder()
    for r in rows:
        name = f"{'🚫 ' if r['is_blocked'] else ''}{r['first_name']} {r['last_name']} · {r['phone']}"
        b.button(text=name[:60], callback_data=f"adm:user:{r['tg_id']}")
    b.adjust(1)
    nav = []
    if page > 0:
        nav.append(IB(text="⬅️", callback_data=f"adm:{prefix}:{page - 1}"))
    if (page + 1) * PAGE < total:
        nav.append(IB(text="➡️", callback_data=f"adm:{prefix}:{page + 1}"))
    if nav:
        b.row(*nav)
    b.row(IB(text="⬅️ Admin panel", callback_data="adm:menu"))
    return b.as_markup()


def user_card(tg_id, blocked):
    b = InlineKeyboardBuilder()
    if blocked:
        b.button(text="✅ Blokdan chiqarish", callback_data=f"adm:unblock:{tg_id}")
    else:
        b.button(text="🚫 Bloklash", callback_data=f"adm:block:{tg_id}")
    b.button(text="📜 Natijalari", callback_data=f"adm:uresults:{tg_id}")
    b.button(text="⬅️ Ro'yxat", callback_data="adm:users:0")
    b.adjust(2, 1)
    return b.as_markup()


def pager(prefix, page, total):
    b = InlineKeyboardBuilder()
    nav = []
    if page > 0:
        nav.append(IB(text="⬅️", callback_data=f"adm:{prefix}:{page - 1}"))
    if (page + 1) * PAGE < total:
        nav.append(IB(text="➡️", callback_data=f"adm:{prefix}:{page + 1}"))
    if nav:
        b.row(*nav)
    b.row(IB(text="⬅️ Admin panel", callback_data="adm:menu"))
    return b.as_markup()


def tests_list(rows):
    b = InlineKeyboardBuilder()
    for r in rows:
        b.button(text=f"{'✅' if r['is_active'] else '⏸'} {r['code']} · {r['title']} · {r['c']} ta",
                 callback_data=f"adm:test:{r['id']}")
    b.button(text="➕ Yangi test", callback_data="adm:newtest")
    b.button(text="⬅️ Admin panel", callback_data="adm:menu")
    b.adjust(1)
    return b.as_markup()


def test_card(tid, active):
    b = InlineKeyboardBuilder()
    b.button(text="➕ Savol qo'shish", callback_data=f"adm:bulk:{tid}")
    b.button(text="👁 Savollar", callback_data=f"adm:qs:{tid}")
    b.button(text="🔑 Kodni o'zgartirish", callback_data=f"adm:code:{tid}")
    b.button(text="⏸ Yashirish" if active else "▶️ Faollashtirish", callback_data=f"adm:toggle:{tid}")
    b.button(text="🗑 O'chirish", callback_data=f"adm:deltest:{tid}")
    b.button(text="⬅️ Testlar", callback_data="adm:tests")
    b.adjust(2, 2, 1, 1)
    return b.as_markup()


def del_confirm(tid):
    b = InlineKeyboardBuilder()
    b.button(text="✅ Ha, o'chirish", callback_data=f"adm:deltest_yes:{tid}")
    b.button(text="❌ Yo'q", callback_data=f"adm:test:{tid}")
    b.adjust(2)
    return b.as_markup()


def qs_kb(qs, tid):
    b = InlineKeyboardBuilder()
    for i, q in enumerate(qs, 1):
        b.button(text=f"🗑 {i}", callback_data=f"adm:delq:{q['id']}:{tid}")
    b.adjust(8)
    b.row(IB(text="⬅️ Test", callback_data=f"adm:test:{tid}"))
    return b.as_markup()


def bulk_done(tid):
    b = InlineKeyboardBuilder()
    b.button(text="✅ Tayyor", callback_data=f"adm:test:{tid}")
    return b.as_markup()


def to_test(tid):
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ Testga qaytish", callback_data=f"adm:test:{tid}")
    return b.as_markup()


def words_kb(rows):
    b = InlineKeyboardBuilder()
    b.button(text="➕ So'z qo'shish", callback_data="adm:addwords")
    for r in rows:
        b.button(text=f"🗑 {r['word']}"[:40], callback_data=f"adm:delword:{r['id']}")
    b.button(text="⬅️ Admin panel", callback_data="adm:menu")
    b.adjust(1)
    return b.as_markup()


def bc_confirm():
    b = InlineKeyboardBuilder()
    b.button(text="✅ Yuborish", callback_data="bc:yes")
    b.button(text="❌ Bekor", callback_data="bc:no")
    b.adjust(2)
    return b.as_markup()
