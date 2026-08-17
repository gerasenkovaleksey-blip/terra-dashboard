"""
Парольная защита отдельных страниц.

Пароль хранится ТОЛЬКО в секретах Streamlit (Manage app → Settings → Secrets),
потому что репозиторий публичный — захардкоженный пароль был бы виден на GitHub.

Это общий пароль, а не учётные записи: он закрывает страницу от случайных глаз,
но не даёт персонального доступа и не пишет журнал входов. Сами данные лежат
в публичных Google-таблицах, так что пароль защищает витрину, а не источник.
"""
import hmac
import streamlit as st

MAX_ATTEMPTS = 5


def require_password(secret_key: str = "control_password",
                     title: str = "Доступ по паролю",
                     hint: str = "") -> bool:
    """
    Показывает форму пароля и возвращает True, только если пароль верный.

    Вызывать в самом начале страницы: пока функция не вернула True,
    ничего не грузить и не показывать.
    """
    state_key = f"auth_ok_{secret_key}"
    tries_key = f"auth_tries_{secret_key}"

    if st.session_state.get(state_key):
        return True

    expected = st.secrets.get(secret_key)
    if not expected:
        st.error(
            f"**Пароль не настроен.** В секретах приложения нет ключа `{secret_key}`.\n\n"
            "Streamlit Cloud → Manage app → Settings → Secrets, добавить строку:\n\n"
            f"```toml\n{secret_key} = \"ваш-пароль\"\n```\n\n"
            "Локально — создать файл `.streamlit/secrets.toml` с той же строкой "
            "(он в .gitignore и в репозиторий не попадёт)."
        )
        st.stop()

    tries = st.session_state.get(tries_key, 0)
    if tries >= MAX_ATTEMPTS:
        st.error("Слишком много неверных попыток. Перезагрузите страницу.")
        st.stop()

    st.markdown(f"### 🔒 {title}")
    if hint:
        st.caption(hint)

    with st.form(f"pwd_form_{secret_key}"):
        entered = st.text_input("Пароль", type="password")
        submitted = st.form_submit_button("Войти")

    if submitted:
        # compare_digest вместо ==: время сравнения не зависит от того,
        # сколько символов совпало, поэтому пароль нельзя подобрать по таймингу
        if hmac.compare_digest(str(entered), str(expected)):
            st.session_state[state_key] = True
            st.session_state.pop(tries_key, None)
            st.rerun()
        else:
            st.session_state[tries_key] = tries + 1
            left = MAX_ATTEMPTS - st.session_state[tries_key]
            st.error(f"Неверный пароль. Осталось попыток: {left}")

    return False
