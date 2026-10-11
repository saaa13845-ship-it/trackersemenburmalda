"""Трекер для Android (Kivy): траты с бюджетом, привычки с планом, напоминания."""
import os
import sqlite3
from datetime import date, datetime, timedelta

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.factory import Factory
from kivy.graphics import Color, RoundedRectangle
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.spinner import Spinner

INK, MUTED = (.07, .09, .15, 1), (.42, .45, .5, 1)
OK, WARN, BAD, ACC = (.18, .62, .42, 1), (.85, .54, 0, 1), (.84, .27, .27, 1), (.18, .44, .93, 1)

CATS = ["Продукты", "Кафе и рестораны", "Транспорт", "Жильё", "Здоровье", "Одежда", "Развлечения",
        "Подписки", "Связь", "Образование", "Табак", "Алкоголь", "Другое"]
TRIGGERS = {"Табак": ("курит", "курен", "сигарет", "вейп", "табак"),
            "Алкоголь": ("алког", "пиво", "вино", "водк", "выпив")}
HARMFUL = [
    (("курит", "курен", "сигарет", "вейп", "табак", "никотин"), [
        (0, "Записывайте каждую сигарету и триггер: кофе, стресс, компания."),
        (1, "Откладывайте каждую на 30 минут, заменяйте водой или жвачкой."),
        (3, "Сократите норму вдвое, уберите сигареты из дома и сумки."),
        (5, "Назначьте день отказа. При тяжёлой тяге обратитесь к врачу.")]),
    (("алког", "пиво", "вино", "водк", "выпив"), [
        (0, "Записывайте, когда и с кем пьёте, и что чувствуете до этого."),
        (1, "Введите дни без алкоголя и замените ритуал."),
        (3, "Не держите алкоголь дома, ограничьте порцию заранее."),
        (5, "Если не получается сократить, обратитесь к врачу.")]),
    (("сладк", "сахар", "фастфуд", "газировк", "перекус"), [
        (0, "Отмечайте, когда тянет: скука, усталость, стресс?"),
        (1, "Замените на фрукты или орехи, уберите сладкое с глаз."),
        (3, "Оставьте сладкое на один запланированный день в неделю."),
        (5, "Закрепите рацион и награждайте себя не едой.")]),
    (("соцсет", "скролл", "телефон", "тикток", "инстаграм", "youtube"), [
        (0, "Включите экранное время и посмотрите реальные цифры."),
        (1, "Уберите приложения с главного экрана, отключите уведомления."),
        (3, "Задайте лимиты и места без телефона: спальня, стол."),
        (5, "Замените вечерний скроллинг книгой или прогулкой.")]),
    (("ногт", "грызть", "кусать"), [
        (0, "Замечайте моменты, когда рука тянется ко рту."),
        (1, "Держите ногти короткими, используйте горький лак."),
        (3, "Дайте рукам занятие: антистресс, чётки."),
        (5, "Награждайте себя за каждую неделю без привычки.")]),
    (("ставк", "казино", "азартн"), [
        (0, "Сегодня же заблокируйте приложения и сайты ставок."),
        (1, "Передайте карты или лимиты человеку, которому доверяете."),
        (3, "Найдите замену азарту: спорт, хобби с новыми целями."),
        (5, "Обратитесь за профессиональной помощью.")]),
]
GENERIC_BAD = [
    (0, "Две недели наблюдайте: когда, где и почему срабатывает привычка."),
    (1, "Придумайте замену, которая даёт то же облегчение."),
    (3, "Уберите триггеры и предметы из поля зрения."),
    (5, "Закрепите результат наградой и расскажите о цели близким.")]
GOOD_STEMS = ("спорт", "бег", "зарядк", "трениров", "воду", "читать", "чтени", "медитац", "сна", "подъём",
              "прогулк", "йога", "англий", "учить", "растяжк")
GOOD_PLAN = [
    (0, "Начните с версии на 2 минуты и привяжите к привычному ритуалу."),
    (1, "Делайте каждый день в одно время и отмечайте выполнение."),
    (3, "Увеличивайте нагрузку на 10-20% в неделю."),
    (5, "Заранее решите, что делать, если пропустили день.")]


def classify(name):
    n = name.lower()
    if any(st in n for stems, _ in HARMFUL for st in stems):
        return "harmful"
    return "good" if any(st in n for st in GOOD_STEMS) else "unknown"


def plan_for(name, kind):
    if kind != "harmful":
        return GOOD_PLAN
    n = name.lower()
    return next((p for stems, p in HARMFUL if any(st in n for st in stems)), GENERIC_BAD)


def level(spent, budget):
    if budget <= 0:
        return 0
    p = spent / budget
    return 2 if p >= 1 else 1 if p >= 0.8 else 0


def money(x):
    return f"{x:,.0f} руб.".replace(",", " ")


def amount(s):
    try:
        v = float(s.replace(",", ".").replace(" ", ""))
        return v if v > 0 else None
    except ValueError:
        return None


def mk(text, color=INK, bold=False, wrap=False):
    lab = Label(text=text, color=color, bold=bold, halign="left", valign="middle",
                size_hint_y=None, height=dp(24), shorten=not wrap, shorten_from="right")
    lab.bind(width=lambda w, v: setattr(w, "text_size", (v, None)))
    if wrap:
        lab.bind(texture_size=lambda w, v: setattr(w, "height", v[1] + dp(2)))
    return lab


def card():
    b = BoxLayout(orientation="vertical", size_hint_y=None, padding=dp(12), spacing=dp(4))
    b.bind(minimum_height=b.setter("height"))
    with b.canvas.before:
        Color(.95, .95, .96, 1)
        rr = RoundedRectangle(radius=[dp(12)])
    b.bind(pos=lambda w, v: setattr(rr, "pos", v), size=lambda w, v: setattr(rr, "size", v))
    return b


def small(text, cb, accent=False):
    b = Factory.Ghost(text=text, height=dp(36), on_release=lambda *_: cb())
    if not accent:
        b.background_color = (.9, .9, .92, 0)
        b.color = MUTED
    return b


def notify(title, msg):
    try:
        from plyer import notification
        notification.notify(title=title, message=msg, timeout=10)
    except Exception:
        pass


KV = """
#:import dp kivy.metrics.dp
<Btn@Button>:
    background_normal: ''
    background_color: .18, .44, .93, 1
    color: 1, 1, 1, 1
    size_hint_y: None
    height: dp(46)
<Ghost@Button>:
    background_normal: ''
    background_color: .9, .9, .92, 1
    color: .07, .09, .15, 1
    size_hint_y: None
    height: dp(42)
<Txt@TextInput>:
    multiline: False
    size_hint_y: None
    height: dp(46)
    padding: dp(12), dp(13)
<Lbl@Label>:
    color: .07, .09, .15, 1
    size_hint_y: None
    height: dp(24)
    halign: 'left'
    valign: 'middle'
    text_size: self.width, None
BoxLayout:
    orientation: 'vertical'
    padding: dp(14)
    spacing: dp(10)
    ScreenManager:
        id: sm
        Screen:
            name: 'exp'
            BoxLayout:
                orientation: 'vertical'
                spacing: dp(8)
                Txt:
                    id: amt
                    hint_text: 'Сумма, руб.'
                    input_filter: 'float'
                Spinner:
                    id: cat
                    size_hint_y: None
                    height: dp(46)
                    background_normal: ''
                    background_color: .9, .9, .92, 1
                    color: .07, .09, .15, 1
                Txt:
                    id: note
                    hint_text: 'Заметка'
                Btn:
                    text: 'Записать'
                    on_release: app.add_expense()
                Lbl:
                    id: err
                    color: .84, .27, .27, 1
                Lbl:
                    id: bl
                    height: dp(44)
                ProgressBar:
                    id: bar
                    max: 1
                    size_hint_y: None
                    height: dp(10)
                BoxLayout:
                    size_hint_y: None
                    height: dp(46)
                    spacing: dp(8)
                    Txt:
                        id: bud
                        hint_text: 'Бюджет на месяц, руб.'
                        input_filter: 'float'
                    Ghost:
                        text: 'Задать'
                        size_hint_x: None
                        width: dp(90)
                        height: dp(46)
                        on_release: app.set_budget()
                ScrollView:
                    GridLayout:
                        id: elist
                        cols: 1
                        size_hint_y: None
                        height: self.minimum_height
                        spacing: dp(6)
        Screen:
            name: 'hab'
            BoxLayout:
                orientation: 'vertical'
                spacing: dp(8)
                Txt:
                    id: hname
                    hint_text: 'Ваша привычка, например: курение'
                Btn:
                    text: 'Добавить привычку'
                    on_release: app.add_habit()
                ScrollView:
                    GridLayout:
                        id: hlist
                        cols: 1
                        size_hint_y: None
                        height: self.minimum_height
                        spacing: dp(8)
        Screen:
            name: 'rem'
            BoxLayout:
                orientation: 'vertical'
                spacing: dp(8)
                Txt:
                    id: rtext
                    hint_text: 'О чём напомнить'
                Txt:
                    id: rat
                    hint_text: 'Время ЧЧ:ММ'
                Btn:
                    text: 'Добавить напоминание'
                    on_release: app.add_reminder()
                Lbl:
                    id: rerr
                    color: .84, .27, .27, 1
                ScrollView:
                    GridLayout:
                        id: rlist
                        cols: 1
                        size_hint_y: None
                        height: self.minimum_height
                        spacing: dp(6)
    BoxLayout:
        size_hint_y: None
        height: dp(46)
        spacing: dp(8)
        Ghost:
            text: 'Траты'
            on_release: sm.current = 'exp'
        Ghost:
            text: 'Привычки'
            on_release: sm.current = 'hab'
        Ghost:
            text: 'Напоминания'
            on_release: sm.current = 'rem'
"""


class Tracker(App):
    def build(s):
        Window.clearcolor = (.98, .98, .99, 1)
        Window.softinput_mode = "below_target"
        s.title = "Tracker"
        s.con = sqlite3.connect(os.path.join(s.user_data_dir, "data.db"))
        s.con.executescript("""
        CREATE TABLE IF NOT EXISTS expenses(id INTEGER PRIMARY KEY, day TEXT, amount REAL, cat TEXT, note TEXT);
        CREATE TABLE IF NOT EXISTS habits(id INTEGER PRIMARY KEY, name TEXT, kind TEXT, start TEXT);
        CREATE TABLE IF NOT EXISTS checkins(habit_id INTEGER, day TEXT, kind TEXT);
        CREATE TABLE IF NOT EXISTS reminders(id INTEGER PRIMARY KEY, text TEXT, at TEXT, fired TEXT);
        CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY, v TEXT);""")
        root = Builder.load_string(KV)
        root.ids.cat.values = CATS
        root.ids.cat.text = CATS[0]
        s.refresh_all()
        Clock.schedule_interval(s.tick, 20)
        return root

    def q(s, sql, *a):
        cur = s.con.execute(sql, a)
        s.con.commit()
        return cur.fetchall()

    def say(s, title, msg):
        p = Popup(title=title, content=mk(msg, wrap=True), size_hint=(.85, None), height=dp(170))
        p.open()
        Clock.schedule_once(lambda dt: p.dismiss(), 5)
        notify(title, msg)

    def refresh_all(s):
        s.refresh_exp()
        s.refresh_habits()
        s.refresh_rem()

    # ---- траты ----
    def month_spent(s):
        first = date.today().replace(day=1).isoformat()
        return s.q("SELECT COALESCE(SUM(amount),0) FROM expenses WHERE day>=?", first)[0][0]

    def budget(s):
        r = s.q("SELECT v FROM settings WHERE k='budget'")
        return float(r[0][0]) if r else 0.0

    def add_expense(s):
        ids = s.root.ids
        a = amount(ids.amt.text)
        if a is None:
            ids.err.text = "Введите сумму больше нуля"
            return
        ids.err.text = ""
        before = level(s.month_spent(), s.budget())
        cat = ids.cat.text
        s.q("INSERT INTO expenses(day, amount, cat, note) VALUES(?,?,?,?)",
            date.today().isoformat(), a, cat, ids.note.text.strip())
        ids.amt.text = ""
        ids.note.text = ""
        if cat in TRIGGERS:
            for hid, name in s.q("SELECT id, name FROM habits WHERE kind='harmful'"):
                if any(t in name.lower() for t in TRIGGERS[cat]):
                    s.q("INSERT INTO checkins VALUES(?,?,'relapse')", hid, date.today().isoformat())
        after = level(s.month_spent(), s.budget())
        if after > before:
            s.say("Бюджет", "Бюджет превышен" if after == 2 else "Потрачено 80% бюджета")
        s.refresh_all()

    def set_budget(s):
        v = amount(s.root.ids.bud.text)
        if v is None:
            s.root.ids.err.text = "Введите бюджет больше нуля"
            return
        s.root.ids.err.text = ""
        s.q("INSERT OR REPLACE INTO settings VALUES('budget', ?)", str(v))
        s.root.ids.bud.text = ""
        s.refresh_exp()

    def edit_expense(s, r):
        box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        amt = Factory.Txt(text=f"{r[2]:g}", input_filter="float")
        cat = Spinner(text=r[3], values=CATS, size_hint_y=None, height=dp(46), background_normal="",
                      background_color=(.9, .9, .92, 1), color=INK)
        note = Factory.Txt(text=r[4] or "")
        err = mk("", color=BAD)
        pop = Popup(title="Изменить трату", content=box, size_hint=(.92, None), height=dp(380))

        def save():
            a = amount(amt.text)
            if a is None:
                err.text = "Введите сумму больше нуля"
                return
            s.q("UPDATE expenses SET amount=?, cat=?, note=? WHERE id=?", a, cat.text, note.text.strip(), r[0])
            pop.dismiss()
            s.refresh_exp()
        for w in (amt, cat, note, err, Factory.Btn(text="Сохранить", on_release=lambda *_: save())):
            box.add_widget(w)
        pop.open()

    def refresh_exp(s):
        ids = s.root.ids
        spent, b = s.month_spent(), s.budget()
        if b > 0:
            lv = level(spent, b)
            ids.bl.text = f"Потрачено {money(spent)} из {money(b)} ({spent / b:.0%})" + \
                          (" - бюджет превышен" if lv == 2 else " - осталось меньше 20%" if lv == 1 else "")
            ids.bl.color = (INK, WARN, BAD)[lv]
            ids.bar.value = min(spent / b, 1)
        else:
            ids.bl.text = f"В этом месяце: {money(spent)}. Задайте бюджет для предупреждений."
            ids.bl.color = MUTED
            ids.bar.value = 0
        ids.elist.clear_widgets()
        rows = s.q("SELECT id, day, amount, cat, note FROM expenses ORDER BY day DESC, id DESC LIMIT 100")
        for r in rows:
            c = card()
            d = datetime.fromisoformat(r[1]).strftime("%d.%m")
            c.add_widget(mk(f"{d}  {money(r[2])}  -  {r[3]}" + (f"  ({r[4]})" if r[4] else ""), bold=True))
            line = BoxLayout(size_hint_y=None, height=dp(36))
            line.add_widget(small("Изменить", lambda r=r: s.edit_expense(r)))
            line.add_widget(small("Удалить", lambda r=r: (s.q("DELETE FROM expenses WHERE id=?", r[0]),
                                                           s.refresh_exp())))
            c.add_widget(line)
            ids.elist.add_widget(c)

    # ---- привычки ----
    def add_habit(s):
        n = s.root.ids.hname.text.strip()
        if n:
            s.q("INSERT INTO habits(name, kind, start) VALUES(?,?,?)", n, classify(n), date.today().isoformat())
            s.root.ids.hname.text = ""
            s.refresh_habits()

    def habit_do(s, sql, *a):
        s.q(sql, *a)
        s.refresh_habits()

    def clean_days(s, hid, start):
        last = s.q("SELECT MAX(day) FROM checkins WHERE habit_id=? AND kind='relapse'", hid)[0][0]
        return (date.today() - date.fromisoformat(max(filter(None, [start, last])))).days

    def streak(s, hid):
        days = {r[0] for r in s.q("SELECT day FROM checkins WHERE habit_id=? AND kind='done'", hid)}
        d = date.today() if date.today().isoformat() in days else date.today() - timedelta(1)
        n = 0
        while d.isoformat() in days:
            n, d = n + 1, d - timedelta(1)
        return n

    def refresh_habits(s):
        lst = s.root.ids.hlist
        lst.clear_widgets()
        today = date.today().isoformat()
        for hid, name, kind, start in s.q("SELECT id, name, kind, start FROM habits ORDER BY id DESC"):
            c = card()
            label, color = {"harmful": ("вредная", BAD), "good": ("полезная", OK),
                            "unknown": ("не определена", MUTED)}[kind]
            c.add_widget(mk(name, bold=True))
            c.add_widget(mk(label, color=color))
            if kind == "harmful":
                c.add_widget(mk(f"{s.clean_days(hid, start)} дн. без срыва", color=MUTED))
                main = ("Срыв", lambda h=hid: s.habit_do("INSERT INTO checkins VALUES(?,?,'relapse')", h, today))
            else:
                c.add_widget(mk(f"Серия: {s.streak(hid)} дн.", color=MUTED))
                main = ("Сделал сегодня", lambda h=hid: s.habit_do(
                    "INSERT INTO checkins SELECT ?,?,'done' WHERE NOT EXISTS "
                    "(SELECT 1 FROM checkins WHERE habit_id=? AND day=? AND kind='done')", h, today, h, today))
            steps = plan_for(name, kind)
            week = (date.today() - date.fromisoformat(start)).days // 7
            cur = max(i for i, (w, _) in enumerate(steps) if w <= week)
            if kind == "unknown":
                c.add_widget(mk("Не удалось определить. Если хотите избавиться от неё, "
                                "нажмите «Тип».", color=MUTED, wrap=True))
            else:
                for i, (w, t) in enumerate(steps):
                    c.add_widget(mk(("> " if i == cur else "") + f"С недели {w + 1}: {t}",
                                    color=INK if i == cur else MUTED, wrap=True))
            row = BoxLayout(size_hint_y=None, height=dp(36))
            flip = "good" if kind == "harmful" else "harmful"
            row.add_widget(small(main[0], main[1], accent=True))
            row.add_widget(small("Тип", lambda h=hid, k=flip: s.habit_do(
                "UPDATE habits SET kind=?, start=? WHERE id=?", k, today, h)))
            row.add_widget(small("Удалить", lambda h=hid: (s.q("DELETE FROM checkins WHERE habit_id=?", h),
                                                            s.habit_do("DELETE FROM habits WHERE id=?", h))))
            c.add_widget(row)
            lst.add_widget(c)

    # ---- напоминания ----
    def add_reminder(s):
        ids = s.root.ids
        try:
            t = datetime.strptime(ids.rat.text.strip(), "%H:%M").strftime("%H:%M")
        except ValueError:
            ids.rerr.text = "Время в формате ЧЧ:ММ, например 09:30"
            return
        if not ids.rtext.text.strip():
            ids.rerr.text = "Введите текст напоминания"
            return
        ids.rerr.text = ""
        s.q("INSERT INTO reminders(text, at) VALUES(?,?)", ids.rtext.text.strip(), t)
        ids.rtext.text = ""
        ids.rat.text = ""
        s.refresh_rem()

    def refresh_rem(s):
        lst = s.root.ids.rlist
        lst.clear_widgets()
        for rid, text, at in s.q("SELECT id, text, at FROM reminders ORDER BY at"):
            c = card()
            c.add_widget(mk(f"{at}  {text}", bold=True))
            c.add_widget(small("Удалить", lambda r=rid: (s.q("DELETE FROM reminders WHERE id=?", r),
                                                          s.refresh_rem())))
            lst.add_widget(c)

    def tick(s, dt):
        now = datetime.now()
        rows = s.q("SELECT id, text FROM reminders WHERE at=? AND COALESCE(fired,'')!=?",
                   now.strftime("%H:%M"), now.date().isoformat())
        for rid, text in rows:
            s.q("UPDATE reminders SET fired=? WHERE id=?", now.date().isoformat(), rid)
            s.say("Напоминание", text)


if __name__ == "__main__":
    Tracker().run()
