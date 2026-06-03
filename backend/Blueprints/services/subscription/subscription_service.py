def has_active_pro_subscription(usuario):
    if usuario is None: return False
    return usuario.plano == "pro" and usuario.status_assinatura == "active"
