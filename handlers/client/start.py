@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, repos: Repos, bot: Bot):
    await state.clear()

    user = await repos.users.get(message.from_user.id)

    if user and user.get("is_blocked"):
        lang = user.get("language", "ru")
        await message.answer(await tt(repos, lang, "blocked"))
        return

    args = message.text.split()
    payload = args[1] if len(args) > 1 else ""

    if payload.startswith("ref_"):
        ref_code = payload[len("ref_"):]
        partner = await repos.staff.get_by_ref_code(ref_code)
        if partner:
            await repos.partners.register_referral(partner["login"], message.from_user.id)

    if user and user.get("gender"):
        lang = user.get("language", "ru")
        if payload.startswith(("cart_", "wish_", "interest_")):
            from handlers.client.cart import handle_deeplink
            await handle_deeplink(message, payload, repos)
            return
        main_menu_text = await tt(repos, lang, "main_menu")
        await message.answer(main_menu_text, reply_markup=await client_menu_kb(repos, message.from_user.id, lang))
        await show_catalog_entry(message, user, repos)
        return

    # Собираем приветствие без тегов <b>
    welcome_parts = []
    for code in ("ru", "en", "uk", "es"):
        part = await repos.texts.get(f"text_welcome_{code}")
        if part:
            # Убираем теги <b> и </b> если они вдруг есть в тексте из базы
            clean_part = part.replace("<b>", "").replace("</b>", "")
            welcome_parts.append(clean_part)
            
    if welcome_parts:
        welcome_text = "\n\n".join(welcome_parts)
    else:
        welcome_text = "Welcome / Добро пожаловать / Вітаємо / Bienvenidos"

    await state.update_data(pending_payload=payload)
    await state.set_state(RegStates.choosing_language)
    await message.answer(welcome_text, reply_markup=kb_language())
