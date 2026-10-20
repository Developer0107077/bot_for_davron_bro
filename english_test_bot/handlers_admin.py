import asyncio
import re
from html import escape

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

import db
import keyboards as kb
from config import ADMIN_IDS
from states import AddWords, BulkQuestions, Broadcast, EditCode, NewTest, Search
from utils import CODE_RE, make_xlsx, norm_code, show

router = Router()
router.message.filter(F.from_user.id.in_(ADMIN_IDS))
router.callback_query.filter(F.from_user.id.in_(ADMIN_IDS))

PAGE = kb.PAGE
L = "ABCD"
# Savol formati uchun regexlar
OPT_RE = re.compile(r"^\s*([A-Da-d])\s*[\)\.\:]\s*(.*)$")          # A) matn  /  a. matn
NUM_RE = re.compile(r"^\s*\d+\s*[\)\.]\s*")                        # 1. savol  /  2) savol
ANS_LINE = re.compile(r"^\s*(?:(?:answer|javob|ans|to'g'ri|togri|correct)\s*[:\-=]?\s*)?([A-Da-d])\s*[\)\.]?\s*$", re.I)
ANS_KW = re.compile(r"^\s*(?:answer|javob|ans|to'g'ri|togri|correct)\s*[:\-=]\s*[A-Da-d]\s*$", re.I)
MARKS = ("*", "✅")                                                # to'g'ri variant belgisi


def fullname(r):
    return f"{escape(r['first_name'] or '')} {escape(r['last_name'] or '')}".strip()


# ---------- Menyu ----------
@router.message(Command("admin"))
@router.message(F.text == "🛠 Admin panel")
async def admin_cmd(m: Message, state: FSMContext):
    await state.clear()
    await m.answer("🛠 <b>Admin panel</b>", reply_markup=kb.admin_menu())


@router.callback_query(F.data == "adm:menu")
async def admin_menu(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await show(cb, "🛠 <b>Admin panel</b>", kb.admin_menu())


@router.callback_query(F.data == "adm:stats")
async def stats(cb: CallbackQuery):
    u = await db.fetchone("SELECT COUNT(*) total, SUM(is_blocked) blocked FROM users")
    today = await db.fetchone("SELECT COUNT(*) c FROM users WHERE date(registered_at)=date('now','localtime')")
    t = await db.fetchone("SELECT COUNT(*) c FROM tests")
    q = await db.fetchone("SELECT COUNT(*) c FROM questions")
    r = await db.fetchone("SELECT COUNT(*) c, ROUND(AVG(percent),1) a FROM results")
    w = await db.fetchone("SELECT COUNT(*) c FROM words")
    await show(cb, (f"📈 <b>Statistika</b>\n\n👥 Foydalanuvchilar: {u['total']} (bugun +{today['c']})\n"
                    f"🚫 Bloklangan: {u['blocked'] or 0}\n📚 Testlar: {t['c']}\n❓ Savollar: {q['c']}\n"
                    f"📝 Topshirilgan testlar: {r['c']}\n📊 O'rtacha natija: {r['a'] or 0}%\n"
                    f"🔤 Lug'at so'zlari: {w['c']}"), kb.back_menu())


# ---------- Foydalanuvchilar ----------
@router.callback_query(F.data.regexp(r"^adm:(users|blocked):\d+$"))
async def users_page(cb: CallbackQuery):
    _, prefix, page = cb.data.split(":")
    page = int(page)
    where = "WHERE is_blocked=1" if prefix == "blocked" else ""
    total = (await db.fetchone(f"SELECT COUNT(*) c FROM users {where}"))["c"]
    rows = await db.fetchall(f"SELECT * FROM users {where} ORDER BY id DESC LIMIT ? OFFSET ?",
                             (PAGE, page * PAGE))
    title = "🚫 Bloklanganlar" if prefix == "blocked" else "👥 Foydalanuvchilar"
    if not rows:
        await show(cb, f"{title}: ro'yxat bo'sh.", kb.back_menu())
        return
    await show(cb, f"{title} — jami {total} (sahifa {page + 1})", kb.users_list(rows, page, total, prefix))


async def user_card(cb: CallbackQuery, tg_id: int):
    u = await db.fetchone("SELECT * FROM users WHERE tg_id=?", (tg_id,))
    if not u:
        await cb.answer("Topilmadi", show_alert=True)
        return
    s = await db.fetchone("SELECT COUNT(*) c, ROUND(AVG(percent),1) a FROM results WHERE tg_id=?", (tg_id,))
    text = (f"👤 <b>{fullname(u)}</b>\n🆔 <code>{u['tg_id']}</code>\n📱 {escape(u['phone'] or '-')}\n"
            f"🔗 {('@' + escape(u['username'])) if u['username'] else '-'}\n"
            f"📅 {u['registered_at'][:16]}\n📝 Testlar: {s['c']} · O'rtacha: {s['a'] or 0}%\n"
            f"Holati: {'🚫 bloklangan' if u['is_blocked'] else '✅ faol'}")
    await show(cb, text, kb.user_card(tg_id, bool(u["is_blocked"])))


@router.callback_query(F.data.startswith("adm:user:"))
async def user_card_cb(cb: CallbackQuery):
    await user_card(cb, int(cb.data.split(":")[2]))


@router.callback_query(F.data.regexp(r"^adm:(block|unblock):\d+$"))
async def block(cb: CallbackQuery, bot: Bot):
    _, action, tg_id = cb.data.split(":")
    tg_id = int(tg_id)
    if tg_id in ADMIN_IDS:
        await cb.answer("Adminni bloklab bo'lmaydi", show_alert=True)
        return
    blocked = action == "block"
    await db.execute("UPDATE users SET is_blocked=? WHERE tg_id=?", (int(blocked), tg_id))
    try:
        await bot.send_message(tg_id, "🚫 Siz bloklandingiz." if blocked else "✅ Siz blokdan chiqarildingiz. /start")
    except Exception:
        pass
    await cb.answer("Bloklandi" if blocked else "Blokdan chiqarildi")
    await user_card(cb, tg_id)


@router.callback_query(F.data.startswith("adm:uresults:"))
async def user_results(cb: CallbackQuery):
    tg_id = int(cb.data.split(":")[2])
    rows = await db.fetchall("SELECT * FROM results WHERE tg_id=? ORDER BY id DESC LIMIT 15", (tg_id,))
    text = "📜 <b>Natijalar:</b>\n\n" + ("\n".join(
        f"• {escape(r['test_title'])}: {r['correct']}/{r['total']} ({r['percent']}%) · {r['finished_at'][:16]}"
        for r in rows) or "Natija yo'q")
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ Orqaga", callback_data=f"adm:user:{tg_id}")
    await show(cb, text, b.as_markup())


@router.callback_query(F.data == "adm:search")
async def search_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(Search.query)
    await show(cb, "🔍 Ism, familiya, telefon, @username yoki Telegram ID yuboring:\n(Bekor qilish: /cancel)")


@router.message(Search.query, F.text)
async def search_do(m: Message, state: FSMContext):
    q = f"%{m.text.strip().lstrip('@')}%"
    rows = await db.fetchall(
        """SELECT * FROM users WHERE first_name LIKE ? OR last_name LIKE ? OR phone LIKE ?
           OR username LIKE ? OR CAST(tg_id AS TEXT) LIKE ? LIMIT 10""", (q, q, q, q, q))
    await state.clear()
    if not rows:
        await m.answer("Hech narsa topilmadi.", reply_markup=kb.back_menu())
        return
    await m.answer(f"🔍 Topildi: {len(rows)} ta", reply_markup=kb.users_list(rows, 0, 0, "users"))


# ---------- Natijalar va Excel ----------
@router.callback_query(F.data.regexp(r"^adm:results:\d+$"))
async def results_page(cb: CallbackQuery):
    page = int(cb.data.split(":")[2])
    total = (await db.fetchone("SELECT COUNT(*) c FROM results"))["c"]
    rows = await db.fetchall(
        """SELECT r.*, u.first_name, u.last_name FROM results r
           LEFT JOIN users u ON u.tg_id = r.tg_id ORDER BY r.id DESC LIMIT ? OFFSET ?""", (PAGE, page * PAGE))
    if not rows:
        await show(cb, "📊 Natijalar yo'q.", kb.back_menu())
        return
    lines = [f"{page * PAGE + i}. {fullname(r)} — {escape(r['test_title'] or '')}: "
             f"<b>{r['correct']}/{r['total']}</b> ({r['percent']}%) · {r['finished_at'][:16]}"
             for i, r in enumerate(rows, 1)]
    await show(cb, f"📊 <b>Natijalar</b> (jami {total})\n\n" + "\n".join(lines), kb.pager("results", page, total))


@router.callback_query(F.data == "adm:top")
async def top(cb: CallbackQuery):
    rows = await db.leaderboard(10)
    text = "🏆 <b>Top-10</b>\n\n" + ("\n".join(
        f"{i}. {fullname(r)} — <b>{r['avg']}%</b> ({r['c']} ta test)" for i, r in enumerate(rows, 1)) or "Bo'sh")
    await show(cb, text, kb.back_menu())


@router.callback_query(F.data == "adm:xl_users")
async def xl_users(cb: CallbackQuery):
    await cb.answer("Tayyorlanmoqda...")
    rows = await db.fetchall("SELECT * FROM users ORDER BY id")
    data = make_xlsx("Foydalanuvchilar",
                     ["№", "Telegram ID", "Ism", "Familiya", "Telefon", "Username", "Holati", "Ro'yxatdan o'tgan"],
                     [(i, r["tg_id"], r["first_name"], r["last_name"], r["phone"], r["username"],
                       "Bloklangan" if r["is_blocked"] else "Faol", r["registered_at"])
                      for i, r in enumerate(rows, 1)])
    await cb.message.answer_document(BufferedInputFile(data, "foydalanuvchilar.xlsx"),
                                     caption=f"👥 Jami: {len(rows)} ta")


@router.callback_query(F.data == "adm:xl_results")
async def xl_results(cb: CallbackQuery):
    await cb.answer("Tayyorlanmoqda...")
    rows = await db.fetchall(
        """SELECT r.*, u.first_name, u.last_name, u.phone FROM results r
           LEFT JOIN users u ON u.tg_id = r.tg_id ORDER BY r.id""")
    data = make_xlsx("Natijalar",
                     ["№", "Telegram ID", "Ism", "Familiya", "Telefon", "Test", "To'g'ri", "Jami", "Foiz (%)", "Sana"],
                     [(i, r["tg_id"], r["first_name"], r["last_name"], r["phone"], r["test_title"],
                       r["correct"], r["total"], r["percent"], r["finished_at"])
                      for i, r in enumerate(rows, 1)])
    await cb.message.answer_document(BufferedInputFile(data, "natijalar.xlsx"),
                                     caption=f"📊 Jami: {len(rows)} ta natija")


# ---------- Testlar ----------
@router.callback_query(F.data == "adm:tests")
async def tests_list(cb: CallbackQuery):
    rows = await db.fetchall(
        """SELECT t.*, COUNT(q.id) AS c FROM tests t LEFT JOIN questions q ON q.test_id=t.id
           GROUP BY t.id ORDER BY t.id DESC""")
    await show(cb, "📚 <b>Testlar</b>" if rows else "📚 Testlar yo'q.", kb.tests_list(rows))


async def test_card(cb: CallbackQuery, tid: int):
    t = await db.fetchone("SELECT * FROM tests WHERE id=?", (tid,))
    if not t:
        await cb.answer("Topilmadi", show_alert=True)
        return
    c = (await db.fetchone("SELECT COUNT(*) c FROM questions WHERE test_id=?", (tid,)))["c"]
    await show(cb, f"📘 <b>{escape(t['title'])}</b>\n🔑 Kod: <code>{escape(t['code'])}</code>\nSavollar: {c}\n"
                   f"Holati: {'✅ faol' if t['is_active'] else '⏸ yashirilgan'}",
               kb.test_card(tid, bool(t["is_active"])))


@router.callback_query(F.data.startswith("adm:test:"))
async def test_card_cb(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await test_card(cb, int(cb.data.split(":")[2]))


@router.callback_query(F.data.startswith("adm:toggle:"))
async def toggle(cb: CallbackQuery):
    tid = int(cb.data.split(":")[2])
    await db.execute("UPDATE tests SET is_active = 1 - is_active WHERE id=?", (tid,))
    await test_card(cb, tid)


@router.callback_query(F.data.startswith("adm:deltest:"))
async def del_test(cb: CallbackQuery):
    await show(cb, "⚠️ Testni va uning barcha savollarini o'chirasizmi?\n(Natijalar saqlanib qoladi)",
               kb.del_confirm(int(cb.data.split(":")[2])))


@router.callback_query(F.data.startswith("adm:deltest_yes:"))
async def del_test_yes(cb: CallbackQuery):
    tid = int(cb.data.split(":")[2])
    await db.execute("DELETE FROM questions WHERE test_id=?", (tid,))
    await db.execute("DELETE FROM tests WHERE id=?", (tid,))
    await cb.answer("🗑 O'chirildi")
    await tests_list(cb)


@router.callback_query(F.data.startswith("adm:qs:"))
async def questions_view(cb: CallbackQuery):
    tid = int(cb.data.split(":")[2])
    qs = await db.fetchall("SELECT * FROM questions WHERE test_id=? ORDER BY id LIMIT 40", (tid,))
    if not qs:
        await cb.answer("Savollar yo'q", show_alert=True)
        return
    lines = [f"{i}. {escape(q['text'][:60])} → {L[q['correct']]}" for i, q in enumerate(qs, 1)]
    await show(cb, "👁 <b>Savollar</b> (o'chirish uchun raqamni bosing)\n\n" + "\n".join(lines), kb.qs_kb(qs, tid))


@router.callback_query(F.data.startswith("adm:delq:"))
async def del_question(cb: CallbackQuery):
    _, _, qid, tid = cb.data.split(":")
    await db.execute("DELETE FROM questions WHERE id=?", (int(qid),))
    await cb.answer("🗑 Savol o'chirildi")
    qs = await db.fetchall("SELECT * FROM questions WHERE test_id=? ORDER BY id LIMIT 40", (int(tid),))
    if qs:
        lines = [f"{i}. {escape(q['text'][:60])} → {L[q['correct']]}" for i, q in enumerate(qs, 1)]
        await show(cb, "👁 <b>Savollar</b>\n\n" + "\n".join(lines), kb.qs_kb(qs, int(tid)))
    else:
        await test_card(cb, int(tid))


# ---------- Yangi test ----------
NEW_TEST_HELP = (
    "➕ <b>Yangi test</b>\n\n"
    "Birinchi qatorga <b>kod - nom</b> yozing, pastiga (xohlasangiz) savollarni qo'shing:\n\n"
    "<code>R3 - Present Simple\n\n"
    "She ___ to school every day.\n"
    "A) go\nB) goes\nC) going\nD) gone\n"
    "Answer: B\n\n"
    "I ___ a book now.\n"
    "A) read\nB) reads\nC) am reading\nD) readed\n"
    "Answer: C</code>\n\n"
    "💡 Faqat <code>R3 - Present Simple</code> yozsangiz ham bo'ladi — savollarni keyin yuborasiz.\n"
    "💡 To'g'ri javobni <code>Answer: B</code> o'rniga variant oxiriga <code>*</code> qo'yib ham belgilash mumkin: "
    "<code>B) goes *</code>\n\n"
    "Bekor qilish: /cancel"
)

BULK_HELP = (
    "📥 Savollarni yuboring (savollar orasida bo'sh qator):\n\n"
    "<code>She ___ to school every day.\n"
    "A) go\nB) goes\nC) going\nD) gone\n"
    "Answer: B</code>\n\n"
    "💡 Javob qatori o'rniga to'g'ri variant oxiriga <code>*</code> qo'ysangiz ham bo'ladi.\n"
    "💡 Bir necha xabar yuborishingiz mumkin. Tugagach «✅ Tayyor» ni bosing."
)


@router.callback_query(F.data == "adm:newtest")
async def new_test(cb: CallbackQuery, state: FSMContext):
    await state.set_state(NewTest.data)
    await show(cb, NEW_TEST_HELP)


@router.message(NewTest.data, F.text)
async def new_test_do(m: Message, state: FSMContext):
    head, _, body = m.text.strip().partition("\n")
    parts = head.split(None, 1)
    code = norm_code(parts[0]) if parts else ""
    if not CODE_RE.match(code):
        await m.answer("❗ Kod noto'g'ri. Faqat lotin harf, raqam, - yoki _ (1–20 belgi). Masalan: <code>R3</code>\n"
                       "Qayta yuboring:")
        return
    if await db.test_by_code(code):
        await m.answer(f"❗ <code>{escape(code)}</code> kodi band. Boshqa kod yuboring:")
        return
    title = (parts[1].lstrip("-–—:| ").strip() if len(parts) > 1 else "") or code
    tid = await db.execute("INSERT INTO tests(code, title) VALUES(?,?)", (code, title[:80]))
    await state.set_state(BulkQuestions.text)
    await state.update_data(test_id=tid)
    head_txt = f"✅ Test yaratildi: <b>{escape(title)}</b> · kod <code>{escape(code)}</code>"
    if body.strip():
        await save_questions(m, tid, body, head_txt)
    else:
        await m.answer(head_txt + "\n\n" + BULK_HELP, reply_markup=kb.bulk_done(tid))


# ---------- Savol qo'shish (ommaviy) ----------
def parse_bulk(text):
    """Matndan savollarni ajratadi. Qaytaradi: ([(savol, a, b, c, d, to'g'ri_indeks)], xato_bloklar_soni).

    Qo'llab-quvvatlanadi:  `1. Savol` raqami, `A)`/`a.`/`A:` variantlari,
    `Answer: B` / `Javob: B` / `B` javob qatori yoki variant oxiridagi `*` / `✅` belgisi.
    """
    ok, bad = [], 0
    q, opts, ans = [], [], None

    def flush():
        nonlocal q, opts, ans, bad
        if q or opts or ans is not None:
            if q and len(opts) == 4 and ans is not None:
                ok.append((" ".join(q), *opts, ans))
            else:
                bad += 1
        q, opts, ans = [], [], None

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        # 4 ta variantdan keyin — javob qatori
        if len(opts) == 4:
            ma = ANS_LINE.match(line)
            if ma:
                ans = "ABCD".index(ma.group(1).upper())
                flush()
                continue
        if ANS_KW.match(line):      # variantlari to'liq bo'lmagan blokning javob qatori — blok xato
            flush()
            continue
        mo = OPT_RE.match(line)
        if mo and q and len(opts) < 4 and mo.group(1).upper() == "ABCD"[len(opts)]:
            t = mo.group(2).strip()
            if t.endswith(MARKS):
                t = t.rstrip("*✅ ").strip()
                ans = len(opts)
            opts.append(t)
            continue
        # oddiy matn — yangi savol boshlanadi (oldingisi tugallanmagan bo'lsa — xato)
        if opts or ans is not None:
            flush()
        q.append(NUM_RE.sub("", line) if not q else line)
    flush()
    return ok, bad


async def save_questions(m: Message, tid: int, text: str, head: str = ""):
    ok, bad = parse_bulk(text)
    if ok:
        await db.executemany("INSERT INTO questions(test_id, text, a, b, c, d, correct) VALUES(?,?,?,?,?,?,?)",
                             [(tid, *x) for x in ok])
    n = (await db.fetchone("SELECT COUNT(*) c FROM questions WHERE test_id=?", (tid,)))["c"]
    lines = [head] if head else []
    lines.append(f"✅ Qo'shildi: {len(ok)} ta savol (testda jami: {n} ta)")
    if bad:
        lines.append(f"⚠️ Formati noto'g'ri bloklar: {bad} ta — o'tkazib yuborildi")
    if not ok:
        lines.append("\n" + BULK_HELP)
    else:
        lines.append("\nYana savol yuborishingiz mumkin yoki «✅ Tayyor» ni bosing.")
    await m.answer("\n".join(lines), reply_markup=kb.bulk_done(tid))


@router.callback_query(F.data.startswith("adm:bulk:"))
async def bulk_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(BulkQuestions.text)
    tid = int(cb.data.split(":")[2])
    await state.update_data(test_id=tid)
    await show(cb, BULK_HELP + "\n\nBekor qilish: /cancel", kb.bulk_done(tid))


@router.message(BulkQuestions.text, F.text)
async def bulk_do(m: Message, state: FSMContext):
    d = await state.get_data()
    await save_questions(m, d["test_id"], m.text)   # holat saqlanadi — yana yuborish mumkin


# ---------- Test kodini o'zgartirish ----------
@router.callback_query(F.data.startswith("adm:code:"))
async def edit_code(cb: CallbackQuery, state: FSMContext):
    tid = int(cb.data.split(":")[2])
    await state.set_state(EditCode.code)
    await state.update_data(test_id=tid)
    await show(cb, "🔑 Yangi kodni yuboring (masalan: <code>R3</code>)\n\nBekor qilish: /cancel")


@router.message(EditCode.code, F.text)
async def edit_code_do(m: Message, state: FSMContext):
    d = await state.get_data()
    code = norm_code(m.text)
    if not CODE_RE.match(code):
        await m.answer("❗ Kod noto'g'ri. Faqat lotin harf, raqam, - yoki _ (1–20 belgi). Qayta yuboring:")
        return
    other = await db.test_by_code(code)
    if other and other["id"] != d["test_id"]:
        await m.answer(f"❗ <code>{escape(code)}</code> kodi band. Boshqa kod yuboring:")
        return
    await db.execute("UPDATE tests SET code=? WHERE id=?", (code, d["test_id"]))
    await state.clear()
    await m.answer(f"✅ Kod o'zgartirildi: <code>{escape(code)}</code>", reply_markup=kb.to_test(d["test_id"]))


# ---------- Lug'at ----------
async def words_view(cb: CallbackQuery):
    n = (await db.fetchone("SELECT COUNT(*) c FROM words"))["c"]
    rows = await db.fetchall("SELECT * FROM words ORDER BY id DESC LIMIT 10")
    await show(cb, f"🔤 <b>Lug'at</b> — jami {n} ta so'z\nOxirgi 10 tasi (o'chirish uchun bosing):", kb.words_kb(rows))


@router.callback_query(F.data == "adm:words")
async def words(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await words_view(cb)


@router.callback_query(F.data.startswith("adm:delword:"))
async def del_word(cb: CallbackQuery):
    await db.execute("DELETE FROM words WHERE id=?", (int(cb.data.split(":")[2]),))
    await cb.answer("🗑 O'chirildi")
    await words_view(cb)


@router.callback_query(F.data == "adm:addwords")
async def add_words(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AddWords.text)
    await show(cb, "So'zlarni yuboring, har biri yangi qatorda:\n\n"
                   "<code>word - tarjima | example sentence</code>\n\nMasalan:\n"
                   "<code>apple - olma | I eat an apple every day.\nbrave - jasur</code>\n\nBekor qilish: /cancel")


@router.message(AddWords.text, F.text)
async def add_words_do(m: Message, state: FSMContext):
    items = []
    for line in m.text.split("\n"):
        if " - " not in line:
            continue
        w, rest = line.split(" - ", 1)
        tr, _, ex = rest.partition("|")
        if w.strip() and tr.strip():
            items.append((w.strip(), tr.strip(), ex.strip()))
    if items:
        await db.executemany("INSERT INTO words(word, translation, example) VALUES(?,?,?)", items)
    await state.clear()
    await m.answer(f"✅ Qo'shildi: {len(items)} ta so'z", reply_markup=kb.back_menu())


# ---------- Xabar yuborish ----------
@router.callback_query(F.data == "adm:bc")
async def bc_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(Broadcast.msg)
    await show(cb, "📢 Barcha foydalanuvchilarga yuboriladigan xabarni yuboring (matn, rasm, video...).\n\nBekor qilish: /cancel")


@router.message(Broadcast.msg)
async def bc_preview(m: Message, state: FSMContext):
    await state.update_data(chat_id=m.chat.id, msg_id=m.message_id)
    await state.set_state(Broadcast.confirm)
    n = (await db.fetchone("SELECT COUNT(*) c FROM users WHERE is_blocked=0"))["c"]
    await m.answer(f"Yuqoridagi xabar {n} ta foydalanuvchiga yuboriladi. Tasdiqlaysizmi?", reply_markup=kb.bc_confirm())


@router.callback_query(Broadcast.confirm, F.data.in_({"bc:yes", "bc:no"}))
async def bc_send(cb: CallbackQuery, state: FSMContext, bot: Bot):
    d = await state.get_data()
    await state.clear()
    if cb.data == "bc:no":
        await show(cb, "❌ Bekor qilindi.", kb.back_menu())
        return
    await show(cb, "⏳ Yuborilmoqda...")
    users = await db.fetchall("SELECT tg_id FROM users WHERE is_blocked=0")
    ok = fail = 0
    for u in users:
        try:
            await bot.copy_message(u["tg_id"], d["chat_id"], d["msg_id"])
            ok += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05)
    await cb.message.answer(f"📢 Yakunlandi.\n✅ Yuborildi: {ok}\n❌ Yetmadi: {fail}", reply_markup=kb.back_menu())
