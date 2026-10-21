# Kwai Insights

App para analisar perfis públicos do Kwai: engajamento, ritmo de postagem, melhores dias e horários, o que nas legendas acompanha mais engajamento, e comparação lado a lado entre concorrentes.

Desenvolvido por **Carolina Campelo** em setembro de 2026 · DUE & Vitória

## O que o app faz

- **🔍 Analisar perfil**: cole o link de qualquer perfil (`https://www.kwai.com/@Embelleze`) ou só o `@`.
  - Números principais: seguidores, vídeo típico, engajamento por 1.000 seguidores, posts por semana, tendência.
  - Linha do tempo de interações e top 10 vídeos (com link).
  - Quando postar: dia da semana, horário e período do mês.
  - Legendas: efeito de cada característica (pergunta, chamada para ação, urgência, maiúsculas…), tipo de conteúdo, gancho, tom, palavras que puxam ou esfriam engajamento, temas automáticos e um simulador de legenda.
  - **CSV tratado e rotulado** para baixar (abre direto no Excel em português).
- **⚔️ Competição**: dois perfis analisados lado a lado, com placar, gráficos sobrepostos e CSV conjunto.

## Estrutura

```
app.py              tela (Streamlit)
config.py           nome do app, autor, logos e cores  ← personalize aqui
kwai/coleta.py      coleta (Selenium para a grade + requests para cada vídeo)
kwai/analise.py     tratamento, rótulos e análises
assets/             logos (logo_due.png, logo_vitoria.png)
requirements.txt    pacotes Python
packages.txt        Chromium para o Streamlit Cloud
```

## Personalizar

1. Autor e data de criação ficam em `config.py` (`AUTOR`, `CRIADO_EM`).
2. Para trocar os logos, substitua os arquivos em `assets/`: `logo_due.png` e `logo_vitoria.png` (também aceita `.jpg` e `.svg`).

## Rodar no computador

Precisa de Python 3.10+ e do Google Chrome instalado.

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Publicar de graça no Streamlit Community Cloud

1. Suba esta pasta para um repositório no GitHub.
2. Entre em [share.streamlit.io](https://share.streamlit.io) com a conta do GitHub.
3. **Create app** → escolha o repositório, branch `main`, arquivo `app.py` → **Deploy**.

O `packages.txt` instala o Chromium automaticamente. A primeira publicação leva alguns minutos.

> Se o Kwai bloquear os servidores do Streamlit Cloud (a coleta volta vazia ou com muitos vídeos inválidos), rode o app no seu computador: o código é o mesmo.

## Como os dados são tratados

- **Interações** = curtidas + comentários.
- **Índice** = interações do vídeo ÷ mediana da conta (1,0 = vídeo típico). Permite comparar contas de tamanhos diferentes.
- **Páginas genéricas** ("Make Everyone Shine"): o app tenta de novo até 3 vezes; o que não vier fica como `valido = não`.
- **Data suspeita**: a grade vem do mais novo ao mais antigo; uma data que foge mais de 45 dias da dos vizinhos é descartada das análises de tempo.
- **Legenda própria**: o prefixo automático do Kwai ("53 Curtidas, 7 Comentários. Kwai video from…") é removido; vídeos sem legenda ficam fora da análise de texto.

Tudo usa mediana, e os efeitos são correlações, não garantia de causa.

## Colunas do CSV

| coluna | o que é |
|---|---|
| `data_publicacao`, `hora_publicacao`, `dia_semana`, `faixa_horario`, `periodo_mes`, `mes` | quando o vídeo foi publicado |
| `curtidas`, `comentarios`, `interacoes` | métricas |
| `indice` | interações ÷ vídeo típico da conta |
| `fora_da_curva` | índice ≥ 2 |
| `coment_por_100_curtidas`, `eng_por_mil_seguidores` | taxas |
| `legenda`, `legenda_propria`, `gancho`, `tom`, `categoria_principal` | texto e classificação |
| `tem_*`, `fala_*`, `caixa_alta`, `cat_*` | rótulos sim/não da legenda |
| `valido`, `data_suspeita`, `fonte_data` | qualidade do dado |
| `id_video`, `link` | identificação |

## Aviso

O app lê apenas dados públicos exibidos nas páginas do Kwai. Use com responsabilidade e respeitando os termos de uso da plataforma.
