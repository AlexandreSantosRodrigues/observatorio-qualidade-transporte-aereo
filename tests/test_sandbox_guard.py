import pytest

from observatorio.bigquery import require_sandbox


class Response:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self.body


class Session:
    def __init__(self, body):
        self.body = body

    def get(self, *args, **kwargs):
        return Response(self.body)


@pytest.mark.parametrize("body", [{"billingEnabled": True}, {}, {"billingEnabled": None}])
def test_faturamento_ativo_ou_desconhecido_bloqueia(body):
    with pytest.raises(RuntimeError):
        require_sandbox("meu-projeto-vra", Session(body))


def test_sandbox_confirmado_e_permitido():
    require_sandbox("meu-projeto-vra", Session({"billingEnabled": False}))


def test_erro_na_api_nao_e_interpretado_como_gratuito():
    class Denied(Session):
        def get(self, *args, **kwargs):
            raise PermissionError("403")
    with pytest.raises(PermissionError):
        require_sandbox("meu-projeto-vra", Denied({}))
