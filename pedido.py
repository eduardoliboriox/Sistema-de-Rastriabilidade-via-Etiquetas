eu quero ajustar algumas coisas no meu sistema, mas como o código é muito grande, vou mandar sempre o que eu quero descrito e parte do meu código e vc vai olhar minha estrutra e me dizer
se antes de fazer o ajuste vc precisa olhar outra parte do meu código, eu mando na hora. 

Sistema de Rastreabilidade via Etiquetas/
├─ static/
    └─ logo.png 
    └─ style.css  
  ├─ qrcodes/
       └─ da.png   
├─ templates/
    ├─ base.html
    ├─ dashboard.html    
    ├─ etiqueta_view.html
    ├─ form.html
    └─ history.html
    ├─ index.html
    ├─ label.html
    └─ movimentar.html
├─ app.py
├─ estrutura.txt
├─ models.db  
├─ README.md
├─ requirements.txt

assim está meu projeto.

solicitação: Modelo	Código	Setor	Fase	Saldo Blank , EU PRECISO ADICIONAR TBM NESSA TABELA A OP, PQ FALANDO COM UM DIRETOR, PARACE QUE É IMPORTANTE. EU SEMPRE QUE
FAÇO UMA NOVA ORDEM DE PRODUÇÃO, EU CADASTRO OP. ENTAO, É APENAS UMA QUESTÃO DE ADICONAR. VOU TE MANDAR O DASHARBORD. HTML. 









EU PENSAVA ISTO SOBRE O SISTEMA Sistema inicia na tela principal (index.html), o primeiro passo é criar uma "nova ordem", tudo começa no PTH. 
vai ser com o modelo 203110776, quantidade do magazine é 50, em FASE vou usar PCB pq é espeficio para o PTH, mas no TIPO DE FASE preciso de PCB tbm para escolher, e ainda tem somente
TOP ONLY E TOP BOTTOM. Tem outros dados, mas esses vc precisa lembrar.
Depois vou em ETIQUETAS, vou colocar que Capacidade por Magazine vou repetir que é 50. Produção Total (placas) vou colocar 300. vou apertar GERAR.
com as etiquetas, vou imprimir a folha. 
Neste ponto, o sistema gerar a quantidade de 300, que aparece na tela DASHBOARD, no setor PTH, no filtro AGUARDANDO. Eu tenho as etiquetas e no momento que ficar pronto o primeiro
magazine vou usar uma etiqueta para este magazine. e vou levar até o Ponto-01 • PTH - para bipar em http://192.168.1.159:5000/movimentar?p=Ponto-01, bipo o qr code, depois Ponto de Marcação:, escolho 
Ponto-01 • PTH na lista. Em Selecione a Ação: vou marcar PRODUÇÃO e apertar REGISTRAR MOVIMENTAÇÃO. 

Ao fazer essa ação, DEU ✅ Produção registrada (50 un.), REAÇÃO AUTOMATICAS: na tela DASHBOARD, no setor PTH, AGUARDANDO, saiu de 300 para 250 na parte de saldo. e PTH, DISPONIVEL
Ficou 50 no saldo que antes tava zero. dentro da tabela na parte fase que poderia ser status tbm, aparece Disponível (Liberado). 

Com isto, entendo que as movimentação deste tipo funcinam perfeitamente. Agora vamos continuar o roteiro e coisas que não estão certas. Quando tem placas disponiveis no PTH, DISPONIVEL, 
o proximo passo do fluxo da produção é levar esse magazine para o Ponto-02 • SMT, para bipar em http://192.168.1.159:5000/movimentar?p=Ponto-02, mas esse caso é de um setor para outro 
DE PTH PARA SMT, ao bipar eu vou usar a marcação RECEBIMENTO. na prática seria assim: bipo o qr code, em Ponto de Marcação: escolho Ponto-02 • SMT, Selecione a Ação: marco RECEBIMENTO
e aperto REGISTRAR MOVIMENTAÇÃO. .TUDO ISTO TA FUNCIONANDO, TA CORRETO ATUALMENET.

MAS EU DESCOBRI QUE EXISTEM ALGUNS POUCOS MODELOS QUE TEM UM FLUXO E ROTEIRO DIFERENTE DO QUE EU PENSAVA, PQ OS SEGUINTES MODELOS 

A29659516, A29659515, A29639902, ARC141295418400.

COMEÇAM NO SETOR SMT E DEPOIS QUE VÃO PRO SETOR PTH, PARA AGUARDANDO, E DEPOIS QUANDO TEM PRODUÇÃO, ELES FICAM PRONTOS LA NO PTH, E DEPOIS ALGUEM DA IM OU PA VAI PEGAR AS PLACAS DISPONIVEIS
DE LA. ENFIM. O SISTEMA NÃO ESTAVA PREPARADO PRA ISTO. PRECISO DE AJUDA COM O AJUSTE.


O QUE PRECISA SER AJUSTADO:

ESSES MODELOS, PRECISAM FAZER ASSIM: EU VOU GERAR ETIQUETAS, VOU IMPRIRMIR, ALGUMA LINHA VAI COMEÇAR A PRODUZIR O MODELO A29659516 POR EXEMPLO NO SETOR SMT, QUANDO FICAR PRONTO VAI 
PARA AGUARDANDO LIBERAÇÃO DO PONTO 03 QUE É DA QUALIDADE DENTRO DO SMT. VAO BIPAR, MARCAR LIBERAR / CQ E ESSE MATERIAL VAI FICAR NO SMT, DISPONIVEL NA TELA DO DASHABOARD. DIGAMOS QUE 
EU PRODUZIR A29659516 SO UM MAGAZINE, 50 PLACAS, E COMO O CQ JA LIBEROU, ESSE MAGAZINE VAI SER LEVADO AO PTH, E AO CHEGAR VAO BIPAR RECEBIMENTO, NESSE MOMENTO. VAI APARECER NO PTH, AGUARDANDO
, E NO SMT, DISPONIVEL, VAI ABATER A QDT QUE FOI PRO PTH DESSE MODELO. 

É IGUAL COMO EU JA TO NO SISTEMA, PTH PRO SMT, MAS INFELIZMENTE ALGUNS POUCOS MODELOS VAO FAZER AO CONTRARIO, O MESMO FLUXO, O SISTEMA JEITO QUE FAZ O PTH PRO SMT, MAS ESSES MODELOS É 
AO CONTRARIO. OS OUTROS MODELOS, VAI SER SEMPRE DO MESMO JEITO QUE JA TA NO SISTEMA DO PTH PRO SMT. 









@app.route("/movimentar", methods=["GET", "POST"])
def movimentar():
    # ==============================================================
    # CAPTURA DO PONTO
    # ==============================================================
    ponto_url = (
        request.form.get("ponto_url") or
        request.args.get("p") or
        request.args.get("ponto")
    )

    model = None
    label = None

    full_code = request.form.get("qr_code") or request.args.get("qr_code")

    # ==============================================================
    # GET – CARREGA MODELO E ETIQUETA EXATA
    # ==============================================================
    if full_code:
        full_code = extract_real_code(full_code)
        if not full_code:
            flash("QR inválido", "danger")
            return redirect(url_for("movimentar", p=ponto_url))

        parts = full_code.split("-")
        base_code = parts[0].upper()
        lote_sufixo = "-".join(parts[1:]) if len(parts) > 1 else None
        lote_formatado = normalize_lote_from_qr(lote_sufixo) if lote_sufixo else None

        conn = get_db()

        # Carrega modelo
        model_row = conn.execute(
            "SELECT * FROM models WHERE UPPER(code)=?",
            (base_code,)
        ).fetchone()

        if not model_row:
            conn.close()
            flash(f"Código '{full_code}' não encontrado.", "danger")
            return redirect(url_for("movimentar", p=ponto_url))

        model = dict(model_row)

        # ==============================
        # LOCALIZA A ETIQUETA CERTA
        # ==============================
        label = None

        if lote_formatado:
            label = conn.execute(
                "SELECT * FROM labels WHERE model_id=? AND lote=? ORDER BY id DESC LIMIT 1",
                (model["id"], lote_formatado)
            ).fetchone()

        # Se não achou → ERRO (NÃO pega última!!!)
        if not label:
            conn.close()
            flash("Etiqueta não encontrada para o lote informado.", "danger")
            return redirect(url_for("movimentar", p=ponto_url))

        label = dict(label)
        conn.close()

    # ==============================================================
    # FUNÇÃO FASE
    # ==============================================================
    def get_fase(ponto, acao):
        if ponto == "Ponto-02" and acao == "RECEBIMENTO":
            return "AGUARDANDO"
        return "DISPONIVEL"

    # ==============================================================
    # POST – MOVIMENTAÇÃO
    # ==============================================================
    if request.method == "POST" and model and label:

        acao = request.form.get("acao")
        acao_norm = acao.strip().upper() if acao else ""
        ponto = request.form.get("ponto") or ponto_url

        setor_origem = label.get("setor_atual")
        quantidade = int(request.form.get("quantidade") or 0)

        conn = get_db()
        remaining = int(label.get("remaining") or label.get("capacidade_magazine") or 0)

        # ==============================================================
        # PONTO-01 — PRODUÇÃO
        # ==============================================================
        if ponto == "Ponto-01" and acao_norm == "PRODUCAO":

            transfer = quantidade if quantidade > 0 else remaining

            if transfer <= 0 or transfer > remaining:
                conn.close()
                flash("Quantidade inválida.", "danger")
                return redirect(url_for("movimentar", p=ponto_url))

            # ABATE PTH
            conn.execute(
                "UPDATE labels SET remaining=?, updated_at=? WHERE id=?",
                (remaining - transfer, datetime.now().isoformat(), label["id"])
            )

            # Nova etiqueta DISPONIVEL em PTH
            conn.execute(
                """
                INSERT INTO labels
                (model_id, lote, producao_total, capacidade_magazine, remaining,
                 created_at, linked_label_id, setor_atual, fase)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    model["id"], label["lote"], transfer, transfer, transfer,
                    datetime.now().isoformat(), label["id"], "PTH", "DISPONIVEL"
                )
            )

            new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            register_movement(
                conn, model["id"], new_id, ponto, acao_norm,
                transfer, setor_origem, "PTH"
            )

            conn.commit()
            conn.close()
            flash(f"Produção registrada ({transfer} un.)", "success")
            return redirect(url_for("movimentar", p=ponto_url))

        # ==============================================================
        # PONTO-02 — RECEBIMENTO SMT (ABATE PTH SEM EXCEÇÃO)
        # ==============================================================
        if ponto == "Ponto-02" and acao_norm == "RECEBIMENTO":

            transfer = int(label.get("capacidade_magazine"))  # SEMPRE a QTD da etiqueta

            # ABATE PTH SEM FALHAR
            novo_remaining = remaining - transfer
            if novo_remaining < 0:
                novo_remaining = 0

            conn.execute(
                "UPDATE labels SET remaining=?, updated_at=? WHERE id=?",
                (novo_remaining, datetime.now().isoformat(), label["id"])
            )

            # CRIA ETIQUETA NO SMT/AGUARDANDO
            conn.execute(
                """
                INSERT INTO labels
                (model_id, lote, producao_total, capacidade_magazine, remaining,
                 created_at, linked_label_id, setor_atual, fase,
                 top_done, bottom_done)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    model["id"], label["lote"],
                    transfer, transfer, transfer,
                    datetime.now().isoformat(),
                    label["id"],
                    "SMT",
                    "AGUARDANDO",
                    label.get("top_done"),
                    label.get("bottom_done")
                )
            )

            new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            register_movement(
                conn, model["id"], new_id, ponto, acao_norm,
                transfer, setor_origem, "SMT"
            )

            conn.commit()
            conn.close()
            flash(f"Recebimento registrado ({transfer} un.)", "success")
            return redirect(url_for("movimentar", p=ponto_url))

        # ==============================================================
        # OUTROS PONTOS (NORMAL)
        # ==============================================================
        transfer = quantidade

        if transfer <= 0:
            conn.close()
            flash("Quantidade inválida.", "danger")
            return redirect(url_for("movimentar", p=ponto_url))

        if transfer > remaining:
            conn.close()
            flash(f"Movimentado {transfer}, mas só existe {remaining}.", "danger")
            return redirect(url_for("movimentar", p=ponto_url))

        novo_remaining = remaining - transfer

        conn.execute(
            "UPDATE labels SET remaining=?, updated_at=? WHERE id=?",
            (novo_remaining, datetime.now().isoformat(), label["id"])
        )

        # DESTINO POR PONTO
        destino_map = {
            "Ponto-03": "SMT",
            "Ponto-04": "IM",
            "Ponto-05": "PA",
            "Ponto-06": "IM",
            "Ponto-07": "ESTOQUE"
        }

        setor_destino = destino_map.get(ponto, setor_origem)

        fase_nova = get_fase(ponto, acao_norm)

        conn.execute(
            """
            INSERT INTO labels
            (model_id, lote, producao_total, capacidade_magazine, remaining,
             created_at, linked_label_id, setor_atual, fase,
             top_done, bottom_done)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                model["id"], label["lote"],
                transfer, transfer, transfer,
                datetime.now().isoformat(),
                label["id"],
                setor_destino,
                fase_nova,
                label.get("top_done"),
                label.get("bottom_done")
            )
        )

        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        register_movement(
            conn, model["id"], new_id, ponto, acao_norm,
            transfer, setor_origem, setor_destino
        )

        conn.commit()
        conn.close()
        flash(f"{acao_norm} registrada ({transfer} un.)", "success")
        return redirect(url_for("movimentar", p=ponto_url))

    # ==============================================================
    # RENDERIZA
    # ==============================================================
    return render_template(
        "movimentar.html",
        model=model,
        label=label,
        ponto=ponto_url,
        hide_top_menu=True
    )

def extract_real_code(qr_text):
    """
    Extrai um código REAL do QR em formato:
        QUALQUER_MODELO-XX-XXX
        
    Onde QUALQUER_MODELO pode ser:
        - Letras (A–Z)
        - Números (0–9)
        - Comprimento variável (1–30 chars)

    E o lote final é sempre:
        2 dígitos - 3 dígitos
    """

    if not qr_text:
        return None

    # Remove espaços e caracteres estranhos
    clean = qr_text.replace(" ", "").replace("Ç", ";").replace("ç", ";")

    # NOVO REGEX → aceita QUALQUER MODELO (1 a 30 chars alpha-numéricos)
    regex = r"([A-Za-z0-9]{1,30}-\d{2}-\d{3})"

    match = re.search(regex, clean)
    if match:
        return match.group(1)

    return None

quando eu gero uma ordem que eu preencho com dados. que vao sair na etiqueta outros eu preencho pq é importante. enfim. tem uma coisa que eu preciso adicionar. 
abaixo de RESISOR(A): EU PRECISO ACIONAR OPERADOR(A):
ENTÃO VAI FICAR 
DATA:
REVISOR(A):
OPERADOR():
OP: 

EU SEI QUE PRECISA DE AJUSTE NA FORM.HTML E PRECISO GARANTIR QUE QUANDO EU APERTAR NOVA ORDEM , EU VOU TER MAIS UM CAMPO PARA PREENCHER, ESSE DE OPERADOR(A)

NAO SEI ONDE TENHO QUE MUDAR, MAS VAMOS LA, VOU TE MANDAR PRIMEIRO FORM.HTML. 















Sistema inicia na tela principal (index.html), o primeiro passo é criar uma "nova ordem", tudo começa no PTH. 
vai ser com o modelo 203110776, quantidade do magazine é 50, em FASE vou usar PCB pq é espeficio para o PTH, mas no TIPO DE FASE preciso de PCB tbm para escolher, e ainda tem somente
TOP ONLY E TOP BOTTOM. Tem outros dados, mas esses vc precisa lembrar.
Depois vou em ETIQUETAS, vou colocar que Capacidade por Magazine vou repetir que é 50. Produção Total (placas) vou colocar 300. vou apertar GERAR.
com as etiquetas, vou imprimir a folha. 
Neste ponto, o sistema gerar a quantidade de 300, que aparece na tela DASHBOARD, no setor PTH, no filtro AGUARDANDO. Eu tenho as etiquetas e no momento que ficar pronto o primeiro
magazine vou usar uma etiqueta para este magazine. e vou levar até o Ponto-01 • PTH - para bipar em http://192.168.1.159:5000/movimentar?p=Ponto-01, bipo o qr code, depois Ponto de Marcação:, escolho 
Ponto-01 • PTH na lista. Em Selecione a Ação: vou marcar PRODUÇÃO e apertar REGISTRAR MOVIMENTAÇÃO. 

Ao fazer essa ação, DEU ✅ Produção registrada (50 un.), REAÇÃO AUTOMATICAS: na tela DASHBOARD, no setor PTH, AGUARDANDO, saiu de 300 para 250 na parte de saldo. e PTH, DISPONIVEL
Ficou 50 no saldo que antes tava zero. dentro da tabela na parte fase que poderia ser status tbm, aparece Disponível (Liberado). 

Com isto, entendo que as movimentação deste tipo funcinam perfeitamente. Agora vamos continuar o roteiro e coisas que não estão certas. Quando tem placas disponiveis no PTH, DISPONIVEL, 
o proximo passo do fluxo da produção é levar esse magazine para o Ponto-02 • SMT, para bipar em http://192.168.1.159:5000/movimentar?p=Ponto-02, mas esse caso é de um setor para outro 
DE PTH PARA SMT, ao bipar eu vou usar a marcação RECEBIMENTO. na prática seria assim: bipo o qr code, em Ponto de Marcação: escolho Ponto-02 • SMT, Selecione a Ação: marco RECEBIMENTO
e aperto REGISTRAR MOVIMENTAÇÃO. 

o que deveria acontecer ? vou dizer. NA TELA DASHBOARD as 50 placas que estavam no PTH, DISPONIVEL, deveria virar zero  e no SETOR SMT, AGUARDANDO, tem que ficar 50 no saldo. Dessa forma,
mas placas vão estar aguardando produção no SMT, e para contar está correta. se saiu do pth, o saldo de la precisa mudar automaticamente.

agora qual é a realidade ? ao bipar RECEBIMENTO NO SMT, PONTO 02, aparece AS 50 PLACAS NO AGUARDANDO. mas o problema é que não abate no saldo do PTH, DISPONIVEL. O SALDO CONTINUA COMO 
SE NADA TIVESSE SAIDO DO SETOR.

DEPOIS EXPLICO MAIS, QUERO AJUSTAR ISTO. SOMENTE ESSAS COISAS. VOU TE MANDARO O ARQUIVO APP.PY. MAS BASTA ME DIZER QUE MANDO O QUE VC QUISER DA MINHA ESTRUTURA. 
 



























TEMOS QUE AJUSTAR A TELA DASHBOARD, VOU EXPLICAR DETALHADAMENTE. atualmente, um dos botões/filtros são:
AGUARDANDO, DISPONIVEL, EXPEDIDO, MOSTRAR TODOS.
AGORA VOU DIZER O QUE DEVERIA SER, MAS ANTES VAMOS RESALTAR QUE ISTO SE SEPARA ANTES PELO FILTRO DE SETORES: PTH, SMT, IM, PA, ESTOQUE, MOSRTRA TODOS. E PORTANTO, ISTO AGUARDANDO, DISPONIVEL, EXPEDIDO, MOSTRAR TODOS. VALE PARA CADA SETORES
NO ENTANTO, A ESTRUTURA CORRETA É:
SELECIONEI SETOR: PTH
AGUARDANDO PRODUÇÃO, PLACAS DISPONIVEIS, MOSTRAR TODOS.
ISTO VALE PARA PTH, SMT, IM, PA
QUANTO AO EXPEDIDO, ISTO VALE QUANDO EU SELECIONAR ESTOQUE, MAS QUANDO EU ESCOLHER ESTOQUE,
EXPEDIDO (SAIU PARA ENTREGA), EU AINDA NÃO TENHO UMA FORMA QUE CONFIRMAR QUE O MATERIAL FOI ENTREGUE, EU NAO FALO COM OS MOTORISTAS, VOU PENSAR NUM JEITO DEPOIS.DeprecationWarning

AGORA VOU EXPLICAR: PASSO A PASSO DA PRODUÇÃO PARA ENTENDERMOS O SISTEMA

GERAR UMA ORDEM DE PRODUÇÃO NO PTH, PARA GERAR AS ETIQUETAS, NESSE MOMENTO, O SISTEMA NO SETOR PTH, NA PARTE AGUARDANDO PRODUÇÃO VAI MARCAR A QUANTIDADE.
ASSIM QUE AS PLACAS FOREM PRODUZIDAS E COLOCADAS NO MAGAZINES VOU BIPAR NO Ponto-01 • PTH, E MARCAR PRODUÇÃO. NESSE MOMENTO, A QDT BIPADA E MARCADA VAI PARA PLACAS DISPONIVEIS, DO SETOR PTH, E
LEMBRAR QUE ABATER A MESMA QDT QUE TAVA NO AGUARDANDO PRODUCAO NO SETOR PTH. 
VOU LEVAR ESSE MAGAZINE DISPONIVEL PARA O SETOR SMT Ponto-02 • SMT, VOU BIPAR E MARCAR RECEBIMENTO. E ESSAS PLACAS VAO PARA AGUARDANDO PRODUÇÃO NO SETOR SMT. isto que ta confundindo o sistema, pq
as etiquetas eram do pth, eu recebi no smt e ainda vou produzir, mas preciso gerar novas etiquetas, no SETOR SMT, mas quando eu gerar as etiquetas, o sistema tbm já vai pensar em 
lançar a qdt no AGUARDANDO PRODUÇÃO DO SMT, a conta vai ficar errada ou precisamos entender o sistema, para nao confundir. É O MESMO MAGAZINE, COMO RECEBI NO OUTRO SETOR, VOU GERAR ETIQUETAS DO SMT.

DEPOIS, A LINHA DO SMT VAI PEGAR O MAGAZINE QUE CHEGOU E VAI PRODUZIR, TEM MODELOS QUE SAO BOTTOM E TOP E OUTROS SOMENTE TOP PARA FICAR REALMENTE PRONTO. DEVIDO A TER ESSE LANCE COM BOTTOM E TOP
TEMOS QUE AJUSTAR A INFORMACAO NA TELA ONDE MOSTRA OS DADOS EM DASHBOARD. ATUALMENTE:  Modelo	Código	Setor	Fase	Saldo, MAS ESSE FASE PODERIA SER STATUS, E SE COLOCASSEMOS
Modelo	Código	Setor	Fase Status	Saldo, e o fase seria BOTTOM ou top, EU CASO EU TENHO FEITO OS DOIS DAS MESMA PLACAS ENTAO BOTTOM E TOP. uma forma de vinculo faz total sentido

quando tiver feito essa prte de producao do smt. as PLACAS FICANDO, AGUARDANDO LIBERAÇÃO CQ. e depois o Ponto-03 • SMT (CQ) vai analisar o magazine e bipar CQ / LIBERAR, nesse momento, as placas
vao PLACAS DISPONIVEIS NO SETOR SMT,

depois alguem da IM OU PA PEGAR ESSE MAGAZINE PRONTO NO SMT. vai produzir, mas eles nao vao trocar a etiquetas do que tava no MAGAZINE QUE ERA DO SMT. primeiro, alguem no Ponto-04 ,
vai bipar RECEBIMENTO, e essas placas ficam AGUARDANDO PRODUÇÃO NO IM OU PA, como eles nao geram etiquetas no momento.mas eu acho até que deveriam. eu so vou saber que as placas estão PRONTAS, QUANDO O 
QUANDO O Ponto-05 • IM/PA (CQ) OU Ponto-06 • IM/PA (CQ) BIPAR A ETIQUETA E MARCAR CQ / LIBERAR, o que indica que as placas estão PLACAS DISPONIVEIS, DENTRO DO IM OU PA, DEPENDE DO SETOR, depois
o ultimo bipe vai ser do estoque quando marcar RECEBIMENTO. como o que eles fazem é sair pra entrega, SE BIPAR RECEBIMENTO no Ponto-07 • Estoque, eu vou pensar que saiu pra entrega. EU VOU TE MANDAR O 
MEU DASHBOARD.HTML. MAS IMAGINE QUE AJUSTE AINDA VOU SER FEITOS NO APP.PY, EU ACHO. VC ME AVISA. 






























EU PRECISO DE MAIS UM AJUSTE REFINADO NA PARTE DE DASHBOARD.HTML E NO GERAL, TALVEZ.
                <option value="">-- Escolher Ponto --</option>
                <option value="Ponto-01">Ponto-01 • PTH </option>
                <option value="Ponto-02">Ponto-02 • SMT </option>
                <option value="Ponto-03">Ponto-03 • SMT (CQ)</option>
                <option value="Ponto-04">Ponto-04 • IM/PA </option>
                <option value="Ponto-05">Ponto-05 • IM/PA (CQ)</option>
                <option value="Ponto-06">Ponto-06 • IM/PA (CQ)</option>
                <option value="Ponto-07">Ponto-07 • Estoque</option>
Esses são os pontos pela empresa
A produção da empresa começa com o Ponto-01 • PTH, primeiro eles vão produzir, bipar produção. depois a placa vão pro SETOR SMT, onde algumas placas
possuem somente a fase top e após a montagem dos componentes estão prontas, mas muitos modelos são bottom e top, e somente quando a linha produzir as duas fases da mesma placa, quero dizer que primeiro fazem a parte de cima, depois eles fazem a parte de baixo, ai a placa ta realmente pronta, Ponto-02 • SMT, significa que produziram (mas ainda precisa saber se é um modelo so de top ou bottom e top), após a produção, as placas estão no status de AGUARDANDO LIBERAÇÃO DA QUALIDADE. ou seja elas estão esperando o Ponto-03 • SMT (CQ) bipar que já estão disponíveis (prontas) e liberadas no setor SMT.

os outros setores da empresa como IM, PA, vão pegar as placas prontas    no setor smt e levar pro setor deles para que colocados, montados outros componentes naquelas placas, e primeiro eles vao receber no Ponto-04 • IM/PA e depois ....vao marcar PRODUCAO, onde igual no setor smt, as placas vão ficar aguardando liberação da qualidade, mas dessa vez, quando estiver prontas, disponives, pode ser liberadas Ponto-05 • IM/PA (CQ) ou Ponto-06 • IM/PA (CQ), e assim que estiver pronto o pessoal do estoque (os motoristas de logística) vao pegar as placas, colocar no caminhão e antes de sair, vao bipar as etiquetas do material que vai sair pra entrega no cliente. no  Ponto-07 • Estoque, e com isto termina tudo.  agora eu preciso que o sistema tem esse raciocino e que a interface tem essas informações, sendo exibidas desse jeito.

APESAR DO MEU APP.PY TER SIDO AJUSTADO COM ESSE PENSAMENTO, A TELA DE DAHSBOARD AINDA NAO É ASSIM. 