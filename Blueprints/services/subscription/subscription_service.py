from extensions import db

def activate_pro_subscription(usuario):
    if usuario.plano == "pro" and usuario.status_assinatura == "active":
        return False 
    
    usuario.plano = "pro"
    usuario.status_assinatura = "active"

    db.session.commit()
    return True

def deactivate_pro_subscription(usuario):
    usuario.plano = "free"
    usuario.status_assinatura = "deactive"

    db.session.commit()

def has_active_pro_subscription(usuario):
    return (
        usuario is not None
        and usuario.plano == "pro"
        and usuario.status_assinatura == "active"
    )