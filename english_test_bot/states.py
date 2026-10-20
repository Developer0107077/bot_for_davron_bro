from aiogram.fsm.state import State, StatesGroup


class Register(StatesGroup):
    first_name = State()
    last_name = State()
    phone = State()


class EnterCode(StatesGroup):
    code = State()


class TakeTest(StatesGroup):
    running = State()


class NewTest(StatesGroup):
    data = State()


class EditCode(StatesGroup):
    code = State()


class BulkQuestions(StatesGroup):
    text = State()


class AddWords(StatesGroup):
    text = State()


class Broadcast(StatesGroup):
    msg = State()
    confirm = State()


class Search(StatesGroup):
    query = State()
