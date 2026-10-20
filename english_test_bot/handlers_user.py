import random
import re
from html import escape

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

import db
import keyboards as kb
from config import ADMIN_IDS
from states import EnterCode, Register, TakeTest
from utils import check_sub, norm_code, show

router = Router()
L = "ABCD"


def grade(p):
    if p >= 90:
        return "🌟 Excellent!"
    if p >= 70:
        return "👍 Good job!"
    if p >= 50:
        return "🙂 Not bad, keep practicing!"
    return "📖 You need more practice!"


async def get_user(tg_id):
    return await db.fetchone("SELECT * FROM users WHERE tg_id=?", (tg_id,))


def menu_for(uid):
    return kb.main_menu(uid in ADMIN_IDS)


async def need_user(m: Message, state: FSMContext):
    if await state.get_state() == EnterCode.code:
        await state.clear()  # menyu tugmasi bosildi — kod kutish bekor
    u = await get_user(m.from_user.id)
    if not u:
        await state.set_state(Register.first_name)
        await m.answer("Avval ro'yxatdan o'ting.\n\n✍️ Ismingizni yuboring:",
                       reply_markup=ReplyKeyboardRemove())
    return u


# ---------- /start va ro'yxatdan o'tish ----------
async def entry(m: Message, state: FSMContext, bot: Bot, tg):
    if not await check_sub(bot, tg.id):
        await m.answer("📢 Botdan foydalanish uchun avval kanalimizga a'zo bo'ling:",
                       reply_markup=kb.sub_kb())
        return
    user = await get_user(tg.id)
    if user:
        await m.answer(f"👋 Welcome back, <b>{escape(user['first_name'])}</b>!\nMenyudan tanlang 👇",
                       reply_markup=menu_for(tg.id))
    else:
        await state.set_state(Register.first_name)
        await m.answer("👋 Assalomu alaykum! Ingliz tili test botiga xush kelibsiz.\n\n"
                       "Ro'yxatdan o'tish uchun <b>ismingizni</b> yuboring:",
                       reply_markup=ReplyKeyboardRemove())


@router.message(CommandStart())
async def start(m: Message, state: FSMContext, bot: Bot):
    await state.clear()
    await entry(m, state, bot, m.from_user)


@router.callback_query(F.data == "chk_sub")
async def chk_sub(cb: CallbackQuery, state: FSMContext, bot: Bot):
    if not await check_sub(bot, cb.from_user.id):
        await cb.answer("Siz hali kanalga a'zo bo'lmadingiz!", show_alert=True)
        return
    await cb.answer()
    try:
        await cb.message.delete()
    except Exception:
        pass
    await entry(cb.message, state, bot, cb.from_user)


def valid_name(t):
    return 2 <= len(t) <= 40 and not any(c.isdigit() for c in t)


def norm_phone(s):
    d = re.sub(r"\D", "", s)
    if len(d) == 9:
        d = "998" + d
    return "+" + d if 11 <= len(d) <= 15 else None


@router.message(Register.first_name, F.text)
async def reg_first(m: Message, state: FSMContext):
    t = m.text.strip()
    if not valid_name(t):
        await m.answer("❗ Ismni to'g'ri kiriting (raqamsiz, 2–40 belgi):")
        return
    await state.update_data(first_name=t[0].upper() + t[1:])
    await state.set_state(Register.last_name)
    await m.answer("✍️ Familiyangizni yuboring:")


@router.message(Register.last_name, F.text)
async def reg_last(m: Message, state: FSMContext):
    t = m.text.strip()
    if not valid_name(t):
        await m.answer("❗ Familiyani to'g'ri kiriting (raqamsiz, 2–40 belgi):")
        return
    await state.update_data(last_name=t[0].upper() + t[1:])
    await state.set_state(Register.phone)
    await m.answer("📱 Telefon raqamingizni yuboring (tugmani bosing yoki +998901234567 ko'rinishida yozing):",
                   reply_markup=kb.PHONE_KB)


async def finish_reg(m: Message, state: FSMContext, phone: str):
    d = await state.get_data()
    await db.execute(
        "INSERT OR IGNORE INTO users(tg_id, first_name, last_name, phone, username) VALUES(?,?,?,?,?)",
        (m.from_user.id, d["first_name"], d["last_name"], phone, m.from_user.username or ""),
    )
    await state.clear()
    await m.answer(f"✅ Ro'yxatdan o'tdingiz, <b>{escape(d['first_name'])}</b>!\n"
                   "Endi testlarni topshirishingiz mumkin 👇", reply_markup=menu_for(m.from_user.id))


@router.message(Register.phone, F.contact)
async def reg_contact(m: Message, state: FSMContext):
    if m.contact.user_id != m.from_user.id:
        await m.answer("❗ Faqat o'zingizning raqamingizni yuboring.")
        return
    phone = norm_phone(m.contact.phone_number)
    await finish_reg(m, state, phone or "+" + m.contact.phone_number.lstrip("+"))


@router.message(Register.phone, F.text)
async def reg_phone_text(m: Message, state: FSMContext):
    phone = norm_phone(m.text)
    if not phone:
        await m.answer("❗ Raqam noto'g'ri. Masalan: +998901234567")
        return
    await finish_reg(m, state, phone)


# ---------- Test topshirish ----------
def test_card_text(t):
    return (f"📘 <b>{escape(t['title'])}</b>\n🔑 Kod: <code>{escape(t['code'])}</code>\n"
            f"Savollar soni: {t['c']}\n\nTayyormisiz?")


async def ask_code(ev, state: FSMContext, bot: Bot, uid: int):
    msg = ev.message if isinstance(ev, CallbackQuery) else ev
    if isinstance(ev, CallbackQuery):
        await ev.answer()
    if not await check_sub(bot, uid):
        await msg.answer("📢 Avval kanalga a'zo bo'ling:", reply_markup=kb.sub_kb())
        return
    await state.set_state(EnterCode.code)
    await msg.answer("🔑 <b>Test kodini yuboring</b>\n\nMasalan: <code>R3</code>\n\nBekor qilish: /cancel")


@router.message(F.text == "📝 Test topshirish")
async def tests_cmd(m: Message, state: FSMContext, bot: Bot):
    if await need_user(m, state):
        await ask_code(m, state, bot, m.from_user.id)


@router.callback_query(F.data == "tests:code")
async def tests_cb(cb: CallbackQuery, state: FSMContext, bot: Bot):
    await state.clear()
    await ask_code(cb, state, bot, cb.from_user.id)


async def send_question(cb: CallbackQuery, state: FSMContext):
    d = await state.get_data()
    q = await db.fetchone("SELECT * FROM questions WHERE id=?", (d["qids"][d["idx"]],))
    opts = "\n".join(f"<b>{L[i]})</b> {escape(q[k])}" for i, k in enumerate("abcd"))
    text = (f"📘 <b>{escape(d['title'])}</b>\nSavol {d['idx'] + 1}/{len(d['qids'])}\n\n"
            f"<b>{escape(q['text'])}</b>\n\n{opts}")
    await show(cb, text, kb.question_kb(d["idx"]))


@router.callback_query(F.data.startswith("go:"))
async def go(cb: CallbackQuery, state: FSMContext):
    tid = int(cb.data.split(":")[1])
    t = await db.fetchone("SELECT * FROM tests WHERE id=? AND is_active=1", (tid,))
    qids = [r["id"] for r in await db.fetchall("SELECT id FROM questions WHERE test_id=?", (tid,))]
    if not t or not qids:
        await cb.answer("Test mavjud emas", show_alert=True)
        return
    random.shuffle(qids)
    await state.set_state(TakeTest.running)
    await state.update_data(test_id=tid, title=t["title"], qids=qids, idx=0, score=0, wrong=[])
    await send_question(cb, state)


@router.callback_query(TakeTest.running, F.data.startswith("ans:"))
async def answer(cb: CallbackQuery, state: FSMContext):
    _, idx, opt = cb.data.split(":")
    idx, opt = int(idx), int(opt)
    d = await state.get_data()
    if idx != d["idx"]:
        await cb.answer("Bu savolga allaqachon javob berilgan")
        return
    q = await db.fetchone("SELECT * FROM questions WHERE id=?", (d["qids"][idx],))
    ok = opt == q["correct"]
    wrong = d["wrong"]
    if not ok:
        wrong.append([q["id"], opt])
    await state.update_data(idx=idx + 1, score=d["score"] + int(ok), wrong=wrong)
    await cb.answer("✅ To'g'ri!" if ok else f"❌ Noto'g'ri. To'g'ri javob: {L[q['correct']]}")
    if idx + 1 >= len(d["qids"]):
        await finish(cb, state)
    else:
        await send_question(cb, state)


async def finish(cb: CallbackQuery, state: FSMContext):
    d = await state.get_data()
    total, score = len(d["qids"]), d["score"]
    pct = round(score / total * 100, 1)
    await db.execute(
        "INSERT INTO results(tg_id, test_id, test_title, correct, total, percent) VALUES(?,?,?,?,?,?)",
        (cb.from_user.id, d["test_id"], d["title"], score, total, pct))
    text = (f"🏁 <b>Test yakunlandi!</b>\n\n📘 {escape(d['title'])}\n"
            f"✅ To'g'ri: {score}/{total}\n📊 Natija: {pct}%\n{grade(pct)}")
    if d["wrong"]:
        text += "\n\n<b>Xatolar tahlili:</b>"
        for qid, ch in d["wrong"][:10]:
            q = await db.fetchone("SELECT * FROM questions WHERE id=?", (qid,))
            if not q:
                continue
            opts = [q["a"], q["b"], q["c"], q["d"]]
            block = (f"\n\n❓ {escape(q['text'])}\n❌ {L[ch]}) {escape(opts[ch])}\n"
                     f"✅ {L[q['correct']]}) {escape(opts[q['correct']])}")
            if len(text) + len(block) > 3800:
                break
            text += block
    await state.clear()
    await show(cb, text, kb.after_test())


@router.callback_query(F.data == "stop")
async def stop(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await show(cb, "🛑 Test to'xtatildi. Natija saqlanmadi.", kb.after_test())


@router.callback_query(F.data.startswith("ans:"))
async def stale_answer(cb: CallbackQuery):
    await cb.answer("Bu test tugagan yoki to'xtatilgan. Qaytadan boshlang.", show_alert=True)


# ---------- Natijalar, reyting, profil ----------
@router.message(F.text == "📊 Natijalarim")
async def my_results(m: Message, state: FSMContext):
    if not await need_user(m, state):
        return
    rows = await db.fetchall("SELECT * FROM results WHERE tg_id=? ORDER BY id DESC LIMIT 10", (m.from_user.id,))
    if not rows:
        await m.answer("Hali test topshirmagansiz.")
        return
    lines = [f"• {escape(r['test_title'])}: <b>{r['correct']}/{r['total']}</b> ({r['percent']}%) · {r['finished_at'][:16]}"
             for r in rows]
    await m.answer("📊 <b>So'nggi natijalaringiz:</b>\n\n" + "\n".join(lines))


@router.message(F.text == "🏆 Reyting")
async def top(m: Message, state: FSMContext):
    if not await need_user(m, state):
        return
    rows = await db.leaderboard(10)
    if not rows:
        await m.answer("Reyting hali bo'sh.")
        return
    medals = ["🥇", "🥈", "🥉"]
    lines = [f"{medals[i] if i < 3 else str(i + 1) + '.'} {escape(r['first_name'])} {escape(r['last_name'])} — "
             f"<b>{r['avg']}%</b> ({r['c']} ta test)" for i, r in enumerate(rows)]
    await m.answer("🏆 <b>Top-10 (o'rtacha natija bo'yicha):</b>\n\n" + "\n".join(lines))


@router.message(F.text == "👤 Profil")
async def profile(m: Message, state: FSMContext):
    u = await need_user(m, state)
    if not u:
        return
    s = await db.fetchone("SELECT COUNT(*) c, ROUND(AVG(percent),1) a FROM results WHERE tg_id=?", (m.from_user.id,))
    await m.answer(f"👤 <b>Profil</b>\n\nIsm: {escape(u['first_name'])}\nFamiliya: {escape(u['last_name'])}\n"
                   f"Telefon: {escape(u['phone'])}\nRo'yxatdan o'tgan: {u['registered_at'][:10]}\n"
                   f"Topshirilgan testlar: {s['c']}\nO'rtacha natija: {s['a'] or 0}%")


@router.message(F.text == "ℹ️ Yordam")
async def help_cmd(m: Message):
    await m.answer("ℹ️ <b>Yordam</b>\n\n📝 Test topshirish — test kodini yuboring (masalan: R3) va savollarga javob bering\n"
                   "📚 Kun so'zi — yangi inglizcha so'zlar\n📊 Natijalarim — so'nggi natijalar\n"
                   "🏆 Reyting — eng yaxshi foydalanuvchilar\n👤 Profil — ma'lumotlaringiz\n\n"
                   "Bekor qilish: /cancel")


# ---------- Kun so'zi ----------
async def send_word(ev):
    w = await db.fetchone("SELECT * FROM words ORDER BY RANDOM() LIMIT 1")
    if not w:
        await show(ev, "Lug'at hozircha bo'sh.")
        return
    text = f"📚 <b>{escape(w['word'])}</b>\n🇺🇿 {escape(w['translation'] or '-')}"
    if w["example"]:
        text += f"\n💬 <i>{escape(w['example'])}</i>"
    await show(ev, text, kb.word_kb())


@router.message(F.text == "📚 Kun so'zi")
async def word_cmd(m: Message, state: FSMContext):
    if await need_user(m, state):
        await send_word(m)


@router.callback_query(F.data == "word:next")
async def word_cb(cb: CallbackQuery):
    await send_word(cb)


# ---------- Qolgan hamma narsa ----------
@router.message(Register.phone)
async def reg_phone_other(m: Message):
    await m.answer("📱 Iltimos, telefon raqamingizni yuboring.", reply_markup=kb.PHONE_KB)


async def open_by_code(m: Message, state: FSMContext, raw: str) -> bool:
    """Kod bo'yicha testni topib, boshlash tugmasini ko'rsatadi. Topilmasa False."""
    t = await db.test_by_code(norm_code(raw), only_active=True)
    if not t or not t["c"]:
        return False
    await state.clear()
    await m.answer(test_card_text(t), reply_markup=kb.start_test(t["id"]))
    return True


@router.message(EnterCode.code, F.text)
async def got_code(m: Message, state: FSMContext):
    if not await open_by_code(m, state, m.text):
        await m.answer(f"❌ <code>{escape(norm_code(m.text)[:30])}</code> kodli test topilmadi.\n"
                       "Kodni tekshirib qayta yuboring yoki /cancel bosing.")


@router.message(EnterCode.code)
async def got_code_other(m: Message):
    await m.answer("🔑 Iltimos, test kodini matn ko'rinishida yuboring. Masalan: <code>R3</code>")


@router.message(StateFilter(None))
async def fallback(m: Message, state: FSMContext):
    if not await get_user(m.from_user.id):
        await m.answer("Boshlash uchun /start bosing.")
        return
    # Foydalanuvchi to'g'ridan-to'g'ri kod yozib yuborsa ham test ochiladi
    if m.text and len(m.text) <= 20 and await open_by_code(m, state, m.text):
        return
    await m.answer("Menyudan tanlang 👇", reply_markup=menu_for(m.from_user.id))
