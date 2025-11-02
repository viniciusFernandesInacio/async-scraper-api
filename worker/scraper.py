"""Scraper direto para Sintegra/GO.
- Envia somente o POST direto (payload "zion") para consultar.asp.
- Faz o parsing do HTML retornado para extrair campos principais.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from common.config import settings
from common.errors import ScrapeError


def mask_cnpj(cnpj_digits: str) -> str:
    d = re.sub(r"\D", "", cnpj_digits)
    return f"{d[0:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:14]}"


def _text_clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _strip_accents(s: str) -> str:
    try:
        return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    except Exception:
        return s


def parse_result_html(html: str) -> dict[str, Any]:
    """Parseia a página de resultado do Sintegra/GO e retorna um dicionário."""
    soup = BeautifulSoup(html, "lxml")

    labels = {
        "cnpj": ["CNPJ"],
        "inscricao_estadual": ["Inscrição Estadual"],
        "razao_social": ["Nome Empresarial", "Razão Social"],
        "contribuinte": ["Contribuinte?"],
        "nome_fantasia": ["Nome Fantasia"],
        "endereco": ["Endereço Estabelecimento", "Endereço"],
        "atividade_principal": ["Atividade Principal"],
        "unidade_auxiliar": ["Unidade Auxiliar"],
        "condicao_uso": ["Condição de Uso"],
        "data_final_contrato": ["Data Final de Contrato"],
        "regime_apuracao": ["Regime de Apuração"],
        "situacao_cadastral": ["Situação Cadastral Vigente", "Situação Cadastral"],
        "data_situacao_cadastral": ["Data desta Situação Cadastral"],
        "data_cadastramento": ["Data de Cadastramento"],
        "operacoes_nf_e": ["Operações com NF-E"],
        "observacoes": ["Observações"],
        "atualizado_em": ["Cadastro Atualizado em"],
        "data_consulta": ["Data da Consulta"],
    }

    data: dict[str, Any] = {}

    def _find_value_for_label(variants: list[str]) -> str | None:
        for variant in variants:
            vnorm = _strip_accents(variant).lower()
            node = soup.find(string=lambda t: t and (vnorm in _strip_accents(_text_clean(t)).lower()))
            if not node:
                continue
            el = node.parent
            sib = el.find_next_sibling()
            if sib:
                txt = _text_clean(sib.get_text(" "))
                if txt:
                    return txt
            tr = el.find_parent("tr")
            if tr:
                cells = tr.find_all(["td", "th"], recursive=False)
                if len(cells) >= 2:
                    txt = _text_clean(cells[1].get_text(" "))
                    if txt:
                        return txt
            for nxt in el.next_elements:
                if nxt is el:
                    continue
                try:
                    txt = _text_clean(nxt.get_text(" ")) if hasattr(nxt, "get_text") else _text_clean(str(nxt))
                except Exception:
                    continue
                if txt and _strip_accents(txt).lower() != vnorm:
                    return txt
        return None

    for key, variants in labels.items():
        val = _find_value_for_label(variants)
        if val:
            data[key] = val

    if "cnpj" not in data:
        m = re.search(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", soup.get_text(" "))
        if m:
            data["cnpj"] = m.group(0)

    return data


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=6),
    reraise=True,
    retry=retry_if_exception_type((httpx.HTTPError, ScrapeError)),
)
def fetch_cnpj_data_zion(cnpj: str) -> dict[str, Any]:
    """Consulta direta com payload "zion" para consultar.asp."""
    headers = {"User-Agent": settings.user_agent}
    timeout = settings.request_timeout_seconds
    masked = mask_cnpj(cnpj)

    base = "https://appasp.sefaz.go.gov.br/sintegra/consulta/"
    default_url = urljoin(base, "default.html")
    consultar_url = urljoin(base, "consultar.asp")

    form_headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://appasp.sefaz.go.gov.br",
        "Referer": default_url,
        **headers,
    }

    payload = {
        "rTipoDoc": "2",
        "tDoc": masked,
        "tCCE": "",
        "tCNPJ": masked,
        "tCPF": "",
        "btCGC": "Consultar",
        "zion.SystemAction": "consultarSintegra()",
        "zion.OnSubmited": "",
        "zion.FormElementPosted": "zionFormID_1",
        "zionPostMethod": "",
        "zionRichValidator": "true",
    }

    with httpx.Client(headers=headers, timeout=timeout, follow_redirects=True) as client:
        r = client.post(consultar_url, data=payload, headers=form_headers)
        r.raise_for_status()
        return parse_result_html(r.text)

