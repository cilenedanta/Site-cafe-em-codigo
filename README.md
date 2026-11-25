# ☕ Café em Código · Notícias do Dia

Dashboard diário com as notícias de quatro temas:

| Seção | O que entra |
|---|---|
| **Tecnologia** | Lançamentos, big techs, produtos e mercado (Tecnoblog, Canaltech, Olhar Digital, The Verge, Ars Technica) |
| **Carreira em Tecnologia** | Vagas, mercado de trabalho e desenvolvimento profissional em TI (Google Notícias, DEV Community, freeCodeCamp) |
| **IA e Impactos** | Inteligência artificial e seus efeitos na sociedade e no trabalho (Google Notícias, MIT Technology Review, The Verge, Ars Technica) |
| **Dados e Fontes** | Ciência de dados, dados abertos e LGPD (Google Notícias, KDnuggets, Towards Data Science, Our World in Data) |

Cada notícia mostra a fonte original e leva direto à matéria. No fim da página há o painel **Fontes monitoradas**, que mostra quantas notícias vieram de cada feed e quais falharam na última coleta.

## Como funciona

```
data/sources.json  ──►  scripts/fetch_news.py  ──►  data/news.json  ──►  index.html
   (lista de feeds)       (coleta RSS/Atom)          (notícias do dia)     (dashboard)
```

- `scripts/fetch_news.py` lê os feeds, descarta notícias com mais de 48h, remove duplicadas e grava `data/news.json`. Usa só a biblioteca padrão do Python.
- O workflow `.github/workflows/update-news.yml` roda **a cada 30 minutos** e faz commit do `news.json` quando há novidade. O GitHub pode atrasar execuções agendadas em alguns minutos nos horários de pico. Também pode ser disparado manualmente em **Actions → Atualizar notícias → Run workflow**.
- `index.html` + `assets/` é um site estático: filtros por seção, busca, filtro de idioma (PT/EN), selo "novo" para os últimos 30 min e tema claro/escuro automático.
- Por padrão o dashboard mostra só as notícias dos **últimos 30 minutos**; o seletor de período amplia para 2h, 6h, 24h ou 48h. A página recarrega os dados sozinha a cada 5 minutos.

## Botão "Atualizar agora"

O botão no topo do dashboard dispara a coleta no GitHub Actions na hora, espera terminar e recarrega as notícias (leva de 1 a 3 minutos, contando a publicação no GitHub Pages).

Na primeira vez ele pede um **token do GitHub** (fine-grained), que fica salvo só no navegador de quem clicou:

1. Acesse https://github.com/settings/personal-access-tokens/new
2. *Repository access* → *Only select repositories* → `Site-cafe-em-codigo`
3. *Permissions* → *Repository permissions* → **Actions: Read and write**
4. Gere o token e cole no dashboard.

O ⚙ ao lado do botão troca ou apaga o token. Sem token, dá para rodar pelo GitHub em **Actions → Atualizar notícias → Run workflow**.

## Rodar localmente

```bash
python scripts/fetch_news.py      # coleta as notícias
python -m http.server 8000        # abre em http://localhost:8000
```

## Publicar

1. Leve estes arquivos para a branch padrão (o agendamento do GitHub Actions só roda na branch padrão).
2. Em **Settings → Pages**, escolha *Deploy from a branch* e a branch padrão, pasta `/ (root)`.
3. Em **Actions**, rode *Atualizar notícias* uma vez para gerar as primeiras notícias.

## Adicionar ou trocar fontes

Edite `data/sources.json`. Cada feed precisa de `name`, `url` (RSS ou Atom) e `lang` (`pt` ou `en`). Para buscas no Google Notícias, use
`https://news.google.com/rss/search?q=SUA+BUSCA+when:1d&hl=pt-BR&gl=BR&ceid=BR:pt-419`.
