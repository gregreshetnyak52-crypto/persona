"""
Анкета для подбора мастера. Встраивается в ConversationHandler booking.py
через состояния RECOMMEND_Q1 и RECOMMEND_Q2.
"""
from telegram import Update
from telegram.helpers import escape_markdown
from telegram.ext import ContextTypes

from data.masters import recommend, MASTERS
from keyboards.builders import (
    recommend_q1_hair_kb,
    recommend_q1_nails_kb,
    recommend_q2_kb,
    recommended_masters_kb,
)


async def show_recommend_q1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать первый вопрос анкеты в зависимости от категории."""
    query = update.callback_query
    category = context.user_data.get("category", "hair")

    if category == "hair":
        kb = recommend_q1_hair_kb()
        text = "Отлично! Что именно планируете?"
    elif category == "nails":
        kb = recommend_q1_nails_kb()
        text = "Что вас интересует?"
    else:
        # для косметологии и массажа — сразу к вопросу об опыте
        context.user_data["desire_tag"] = category
        await show_recommend_q2(update, context)
        return

    await query.edit_message_text(text, reply_markup=kb)


async def show_recommend_q2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.edit_message_text(
        "Какой мастер вам больше подойдёт?",
        reply_markup=recommend_q2_kb(),
    )


async def handle_recommend_q1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    tag = query.data.replace("rq1_", "")
    context.user_data["desire_tag"] = tag
    await show_recommend_q2(update, context)


async def handle_recommend_q2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    pref = query.data.replace("rq2_", "")  # any | experienced | top
    context.user_data["experience_pref"] = pref

    category = context.user_data.get("category", "hair")
    desire_tag = context.user_data.get("desire_tag", "")
    recommended = recommend(category, desire_tag, pref)

    if not recommended:
        await query.edit_message_text(
            "К сожалению, не удалось подобрать мастера по вашим критериям. "
            "Позвоните нам: +7 (495) 120-76-67"
        )
        return

    lines = ["🌟 *Рекомендуем вам:*\n"]
    for m in recommended:
        lines.append(f"*{escape_markdown(m['name'], version=1)}*\n_{m['bio']}_\n")

    context.user_data["recommended_masters"] = recommended
    await query.edit_message_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=recommended_masters_kb(recommended),
    )


def get_master_profile_by_name(name: str) -> dict | None:
    for m in MASTERS:
        if m["name"] == name:
            return m
    return None
