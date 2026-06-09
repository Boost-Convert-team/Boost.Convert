PROCESSING_ACTIVITIES = {
    "cadastro": {
        "purpose": "Criar e manter conta do usuario.",
        "data": ["email", "hash_de_senha"],
        "legal_basis": "execucao_de_contrato",
    },
    "login": {
        "purpose": "Autenticar usuario e manter sessao.",
        "data": ["email", "hash_de_senha", "google_id", "session_id"],
        "legal_basis": "execucao_de_contrato",
    },
    "recuperacao_de_senha": {
        "purpose": "Permitir recuperacao de acesso quando implementada.",
        "data": ["email", "token_temporario"],
        "legal_basis": "execucao_de_contrato",
    },
    "pagamentos": {
        "purpose": "Ativar plano contratado e registrar status de assinatura.",
        "data": ["user_id", "status_assinatura", "plano"],
        "legal_basis": "execucao_de_contrato",
    },
    "processamento_de_arquivos": {
        "purpose": "Converter arquivos enviados pelo usuario.",
        "data": ["arquivo_temporario", "tipo_de_conversao", "status"],
        "legal_basis": "execucao_de_contrato",
    },
    "historico_de_conversoes": {
        "purpose": "Exibir status recente e cumprir auditoria minima.",
        "data": ["usuario_ou_sessao", "data", "tipo_de_conversao", "status"],
        "legal_basis": "legitimo_interesse",
    },
}


def get_processing_activities():
    return PROCESSING_ACTIVITIES.copy()
