"""Testes do parser de HTML do scraper.
- Exercita variacoes de markup para conferir extracao de campos.
"""

from worker.scraper import parse_result_html


def test_parse_result_html_basic():
    html = """
    <html><body>
      <div>
        <b>CNPJ</b><div>00.022.244/0001-75</div>
      </div>
      <div>
        <b>Nome Empresarial</b><div>COPOCENTRO INDUSTRIA DE PLASTICOS LTDA FALIDO</div>
      </div>
      <div>
        <b>Endereço Estabelecimento</b><div>RUA VP 3D, ANAPOLIS GO</div>
      </div>
      <div>
        <b>Situação Cadastral Vigente</b><div>Suspenso - NÃO HABILITADO</div>
      </div>
    </body></html>
    """

    data = parse_result_html(html)
    assert data["cnpj"] == "00.022.244/0001-75"
    assert "COPOCENTRO" in data["razao_social"]
    assert "ANAPOLIS" in data["endereco"].upper()


def test_parse_result_html_variants():
    html = """
    <html><body>
      <div>
        <b>Razão Social</b><div>ACME LTDA</div>
      </div>
      <div>
        <b>Endereço</b><div>RUA TESTE, GOIANIA - GO</div>
      </div>
      <div>
        <b>CNPJ</b><div>00.000.000/0001-00</div>
      </div>
      <div>
        <b>Situação Cadastral</b><div>HABILITADO</div>
      </div>
    </body></html>
    """
    data = parse_result_html(html)
    assert data["cnpj"] == "00.000.000/0001-00"
    assert data["razao_social"].startswith("ACME")
    assert data["situacao_cadastral"].startswith("HABILIT")
