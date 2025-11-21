#!/usr/bin/env python3
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, abort
from datetime import datetime
import sqlite3, os, qrcode
from io import BytesIO
import socket
import re

app = Flask(__name__)
app.secret_key = "chave_super_secreta_trocar"
DB_PATH = "models.db"

# ---------------- Banco de Dados ----------------
def init_db():
    if os.path.exists(DB_PATH):
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            model_name TEXT,
            cliente TEXT,
            linha TEXT,
            turno TEXT,
            data TEXT,
            lote TEXT,
            quantidade TEXT,
            revisora TEXT,
            horario TEXT,
            po TEXT,
            op TEXT,
            status_cq TEXT,
            processo TEXT,
            obs TEXT,
            setor TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id INTEGER,
            changed_at TEXT,
            changed_by TEXT,
            change_text TEXT,
            FOREIGN KEY(model_id) REFERENCES models(id)
        )
    ''')
    c.execute('''
        CREATE TABLE labels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id INTEGER,
            lote TEXT,
            producao_total INTEGER,
            capacidade_magazine INTEGER,
            created_at TEXT,
            linked_label_id INTEGER,
            setor_atual TEXT,
            FOREIGN KEY(model_id) REFERENCES models(id),
            FOREIGN KEY(linked_label_id) REFERENCES labels(id)
        )
    ''')
    c.execute('''
        CREATE TABLE movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id INTEGER,
            label_id INTEGER,
            ponto TEXT,
            acao TEXT,
            quantidade INTEGER,
            from_setor TEXT,
            to_setor TEXT,
            created_at TEXT,
            created_by TEXT,
            FOREIGN KEY(model_id) REFERENCES models(id),
            FOREIGN KEY(label_id) REFERENCES labels(id)
        )
    ''')
    conn.commit()
    conn.close()

def add_missing_column():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("PRAGMA table_info(models);")
    columns = [col[1] for col in c.fetchall()]

    # Colunas existentes
    if "op" not in columns:
        c.execute("ALTER TABLE models ADD COLUMN op TEXT;")
    if "setor" not in columns:
        c.execute("ALTER TABLE models ADD COLUMN setor TEXT;")

    if "fase" not in columns:
        c.execute("ALTER TABLE models ADD COLUMN fase TEXT;")

    if "phase_type" not in columns:
        c.execute("ALTER TABLE models ADD COLUMN phase_type TEXT DEFAULT 'TOP_ONLY';")

    if "operadora" not in columns:
        c.execute("ALTER TABLE models ADD COLUMN operadora TEXT;")

    conn.commit()   
    conn.close()

def add_missing_table_labels():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='labels';")
    if not c.fetchone():
        c.execute("""
            CREATE TABLE labels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_id INTEGER,
                lote TEXT,
                producao_total INTEGER,
                capacidade_magazine INTEGER,
                remaining INTEGER,
                created_at TEXT,
                linked_label_id INTEGER,
                setor_atual TEXT,
                fase TEXT,
                top_done INTEGER DEFAULT 0,
                bottom_done INTEGER DEFAULT 0,
                status TEXT DEFAULT 'ATIVO',
                FOREIGN KEY(model_id) REFERENCES models(id),
                FOREIGN KEY(linked_label_id) REFERENCES labels(id)
            )
        """)
        conn.commit()
    else:
        c.execute("PRAGMA table_info(labels);")
        columns = [col[1] for col in c.fetchall()]
        if "linked_label_id" not in columns:
            c.execute("ALTER TABLE labels ADD COLUMN linked_label_id INTEGER REFERENCES labels(id);")
        if "setor_atual" not in columns:
            c.execute("ALTER TABLE labels ADD COLUMN setor_atual TEXT;")
        if "fase" not in columns:
            c.execute("ALTER TABLE labels ADD COLUMN fase TEXT;")
        if "remaining" not in columns:
            c.execute("ALTER TABLE labels ADD COLUMN remaining INTEGER;")
            # Inicializa remaining com capacidade_magazine para registros antigos
            c.execute("UPDATE labels SET remaining = capacidade_magazine WHERE remaining IS NULL;")
        if "top_done" not in columns:
            c.execute("ALTER TABLE labels ADD COLUMN top_done INTEGER DEFAULT 0;")
        if "bottom_done" not in columns:
            c.execute("ALTER TABLE labels ADD COLUMN bottom_done INTEGER DEFAULT 0;")
        if "status" not in columns:
            c.execute("ALTER TABLE labels ADD COLUMN status TEXT DEFAULT 'ATIVO';")
        if "updated_at" not in columns:
            c.execute("ALTER TABLE labels ADD COLUMN updated_at TEXT;")
        conn.commit()
    conn.close()

def add_missing_table_movements():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='movements';")
    if not c.fetchone():
        c.execute('''
            CREATE TABLE movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_id INTEGER,
                label_id INTEGER,
                ponto TEXT,
                acao TEXT,
                quantidade INTEGER,
                from_setor TEXT,
                to_setor TEXT,
                created_at TEXT,
                created_by TEXT
            )
        ''')
        conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

with app.app_context():
    init_db()
    add_missing_column()
    add_missing_table_labels()
    add_missing_table_movements()

# ---------------- Regras de Ponto / Roteiro ----------------
# Definir um mapeamento básico dos pontos para setores.
POINT_RULES = {
    "Ponto-01": {"setor": "PTH", "type": "porta"},
    "Ponto-02": {"setor": "SMT", "type": "porta"},
    "Ponto-03": {"setor": "SMT", "type": "qualidade"},
    "Ponto-04": {"setor": "IM/PA", "type": "porta"},
    "Ponto-05": {"setor": "IM/PA", "type": "qualidade"},
    "Ponto-06": {"setor": "IM/PA", "type": "qualidade"},
    "Ponto-07": {"setor": "ESTOQUE", "type": "expedicao"},
}

def normalize_lote_from_qr(lote_sufixo):
    """Converte o sufixo vindo do QR (ex: '08-504' ou '08-504-xyz') para o formato salvo '08 / 504' (aprox)."""
    if not lote_sufixo:
        return None
    parts = lote_sufixo.split("-")
    if len(parts) == 1:
        return parts[0].replace('-', ' / ').strip()
    first = parts[0].strip()
    second = parts[1].strip() if len(parts) > 1 else ""
    return f"{first} / {second}"

def find_label(conn, model_id, lote_formatado):
    """Procura uma label do model_id com lote exatamente igual (tente correspondência direta)."""
    if not lote_formatado:
        return None
    cur = conn.execute("SELECT * FROM labels WHERE model_id=? AND lote=?", (model_id, lote_formatado)).fetchone()
    if cur:
        return dict(cur)
    # tentativa de correspondência mais permissiva (removendo espaços)
    simple = lote_formatado.replace(" ", "")
    cur2 = conn.execute("SELECT * FROM labels WHERE model_id=? AND REPLACE(lote,' ','') LIKE ?", (model_id, f"%{simple}%")).fetchone()
    if cur2:
        return dict(cur2)
    return None

def register_movement(conn, model_id, label_id, ponto, acao, quantidade, from_setor, to_setor, created_by="terminal_movimentacao"):
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO movements (model_id, label_id, ponto, acao, quantidade, from_setor, to_setor, created_at, created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (model_id, label_id, ponto, acao, quantidade, from_setor, to_setor, now, created_by)
    )

# ---------------- Rotas ----------------
@app.route("/")
def index():
    search = request.args.get("search", "").strip()
    conn = get_db()
    if search:
        query = """
            SELECT * FROM models 
            WHERE code LIKE ? OR model_name LIKE ? OR cliente LIKE ?
            ORDER BY id DESC
        """
        models = conn.execute(query, (f"%{search}%", f"%{search}%", f"%{search}%")).fetchall()
    else:
        models = conn.execute("SELECT * FROM models ORDER BY id DESC").fetchall()
    conn.close()

    def format_updated_at(value):
        if not value:
            return ""
        try:
            s = str(value).replace("T", " ")
            s_short = s.split(".")[0].split("+")[0].split("Z")[0].strip()
            dt = datetime.strptime(s_short, "%Y-%m-%d %H:%M:%S")
            return dt.strftime("%d/%m/%Y às %H:%M:%S")
        except:
            try:
                dt2 = datetime.fromisoformat(str(value))
                return dt2.strftime("%d/%m/%Y às %H:%M:%S")
            except:
                return str(value)

    models = [dict(m) for m in models]
    for m in models:
        m["updated_at_formatted"] = format_updated_at(m.get("updated_at"))

    return render_template("index.html", models=models, search=search)

@app.route("/new", methods=["GET", "POST"])
def new():
    if request.method == "POST":
        f = request.form
        conn = get_db()
        try:
            conn.execute(
                """INSERT INTO models 
                    (code, model_name, cliente, linha, setor, fase, phase_type, turno, data, lote, quantidade, revisora, operadora, horario, po, op, status_cq, processo, obs, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                (
                    f.get("code", ""),
                    f.get("model_name", ""),
                    f.get("cliente", ""),
                    f.get("linha", ""),
                    f.get("setor", ""),
                    f.get("fase", ""),  
                    f.get("phase_type", "TOP_ONLY"), 
                    f.get("turno", ""),
                    f.get("data") or datetime.now().strftime("%d/%m/%Y"),
                    f"{f.get('lote_num', '').strip()} / {f.get('lote_padrao', '').strip()}",
                    f.get("quantidade", ""),
                    f.get("revisora", ""),
                    f.get("operadora", ""),
                    f.get("horario", ""),
                    f.get("po", ""),
                    f.get("op", ""),
                    ",".join(request.form.getlist("status_cq")),
                    ",".join(request.form.getlist("processo")),
                    f.get("obs", ""),
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                )
            )
            conn.commit()
            flash("Modelo cadastrado com sucesso!", "success")
        except sqlite3.Error as e:
            flash(f"Erro ao salvar: {e}", "danger")

        finally:
            conn.close()
        return redirect(url_for("index"))
    return render_template("form.html", model=None)

@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit(id):
    conn = get_db()
    try:
        model = conn.execute("SELECT * FROM models WHERE id=?", (id,)).fetchone()
        if not model:
            conn.close()
            abort(404)

        # -----------------------------------------------
        # SE FOR POST: atualizar registro
        # -----------------------------------------------
        if request.method == "POST":
            f = request.form

            lote_num = f.get("lote_num", "").strip()
            lote_padrao = f.get("lote_padrao", "").strip()
            lote_final = f"{lote_num} / {lote_padrao}"

            try:
                conn.execute("""
                    UPDATE models 
                    SET code=?, model_name=?, cliente=?, linha=?, setor=?, fase=?, phase_type=?, turno=?, data=?, 
                        lote=?, quantidade=?, revisora=?, operadora=?, horario=?, po=?, op=?, status_cq=?, processo=?, obs=?, updated_at=?
                    WHERE id=?
                """, (
                    f["code"],
                    f["model_name"],
                    f["cliente"],
                    f["linha"],
                    f.get("setor", ""),
                    f.get("fase", ""),
                    f.get("phase_type", "TOP_ONLY"),
                    f["turno"],
                    f["data"],
                    lote_final,
                    f["quantidade"],
                    f["revisora"],
                    f["operadora"],
                    f["horario"],
                    f["po"],
                    f.get("op", ""),
                    ",".join(request.form.getlist("status_cq")),
                    ",".join(request.form.getlist("processo")),
                    f["obs"],
                    datetime.now().isoformat(),
                    id
                ))
            except sqlite3.IntegrityError:
                flash("❌ Já existe um modelo com este CODE. Escolha outro.", "danger")
                return redirect(url_for("edit", id=id))

            # REGISTRAR HISTÓRICO
            conn.execute(
                "INSERT INTO history (model_id, changed_at, changed_by, change_text) VALUES (?, ?, ?, ?)",
                (id, datetime.now().isoformat(), "web_user", "Edição de modelo")
            )

            conn.commit()
            flash("Modelo atualizado com sucesso!", "success")
            return redirect(url_for("index"))

        # -----------------------------------------------
        # SE FOR GET: carregar form.html com modelo
        # -----------------------------------------------
        lote_num, lote_padrao = "", ""
        if model["lote"]:
            partes = [p.strip() for p in model["lote"].split("/")]
            if len(partes) >= 1:
                lote_num = partes[0]
            if len(partes) >= 2:
                lote_padrao = partes[1]

        return render_template("form.html", model=model, lote_num=lote_num, lote_padrao=lote_padrao)

    except Exception as e:
        print("Erro no edit():", e)
        raise e
    finally:
        conn.close()

@app.route("/view/<int:id>", methods=["GET", "POST"])
def view_label(id):
    with get_db() as conn:
        model = conn.execute("SELECT * FROM models WHERE id=?", (id,)).fetchone()
    existing_labels = conn.execute("SELECT * FROM labels WHERE model_id=? ORDER BY created_at DESC", (id,)).fetchall()
    conn.close()
    if not model:
        abort(404)

    etiquetas_por_folha = 3
    producao_total = None
    capacidade_magazine = None
    lotes = []

    if request.method == "POST":
        try:
            producao_total = int(request.form.get("producao_total", 0))
            capacidade_magazine = int(request.form.get("capacidade_magazine", 1))
            if capacidade_magazine <= 0:
                capacidade_magazine = 1

            total_etiquetas = (producao_total + capacidade_magazine - 1) // capacidade_magazine
            total_folhas = (total_etiquetas + etiquetas_por_folha - 1) // etiquetas_por_folha

            try:
                parte_num, parte_padrao = [x.strip() for x in model['lote'].split('/')[:2]]
                lote_inicial = int(parte_num)
                padrao = parte_padrao
            except:
                lote_inicial = 1
                padrao = "900"

            lotes = [f"{lote_inicial + i:02d} / {padrao}" for i in range(total_etiquetas)]

            linked_label_id = request.form.get("linked_label_id") or None

            conn = get_db()
            for lote in lotes:
                conn.execute("""
                    INSERT INTO labels 
                        (model_id, lote, producao_total, capacidade_magazine, remaining, created_at, linked_label_id, setor_atual, fase)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    id,
                    lote,
                    producao_total,
                    capacidade_magazine,
                    capacidade_magazine,
                    datetime.now().isoformat(),
                    linked_label_id,
                    model["setor"] if model["setor"] else "PTH",
                    "AGUARDANDO"
                ))
            conn.commit()
            conn.close()

            flash(f"Produção: {producao_total} placas → {total_etiquetas} etiquetas → {total_folhas} folhas. Etiquetas salvas no histórico.", "info")

        except ValueError:
            flash("⚠️ Digite valores válidos para produção e capacidade.", "danger")

    return render_template("label.html", m=model, lotes=lotes, existing_labels=existing_labels)

@app.route("/qr/<string:code>")
def qr(code):
    import socket
    from io import BytesIO
    import qrcode

    # 🔹 Detecta o IP local da máquina automaticamente
    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except:
        local_ip = "127.0.0.1"

    # 🔹 Gera a URL completa (agora compatível com códigos únicos)
    # OBS: os terminais/físicos onde o QR será lido podem adicionar o parâmetro ?p=Ponto-01
    qr_url = f"http://{local_ip}:5000/movimentar/{code.strip()}"

    img = qrcode.make(qr_url)
    buf = BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")

@app.route("/movimentar", methods=["GET", "POST"])
def movimentar():
    ponto_url = request.form.get("ponto_url") or request.args.get("p") or request.args.get("ponto")
    model = None
    label = None
    full_code = request.form.get("qr_code") or request.args.get("qr_code")
    clean_display_code = clean_display_qr(full_code)


    SMT_FIRST_MODELS = ["A29659516", "A29659515", "A29639902", "ARC141295418400"]

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
        model_row = conn.execute("SELECT * FROM models WHERE UPPER(code)=?", (base_code,)).fetchone()
        if not model_row:
            conn.close()
            flash(f"Código '{full_code}' não encontrado.", "danger")
            return redirect(url_for("movimentar", p=ponto_url))
        model = dict(model_row)

        if lote_formatado:
            label_row = conn.execute(
                "SELECT * FROM labels WHERE model_id=? AND lote=? ORDER BY id DESC LIMIT 1",
                (model["id"], lote_formatado)
            ).fetchone()
            if label_row:
                label = dict(label_row)
        if not label:
            conn.close()
            flash("Etiqueta não encontrada para o lote informado.", "danger")
            return redirect(url_for("movimentar", p=ponto_url))
        conn.close()

    def get_fase(ponto, acao):
        if ponto == "Ponto-02" and acao == "RECEBIMENTO":
            return "AGUARDANDO"
        return "DISPONIVEL"

    if request.method == "POST" and model and label:
        acao = (request.form.get("acao") or "").strip().upper()
        ponto = request.form.get("ponto") or ponto_url
        conn = get_db()
        setor_origem = label.get("setor_atual")
        capacidade = int(label.get("capacidade_magazine") or 0)
        remaining = int(label.get("remaining") or capacidade)
        quantidade = int(request.form.get("quantidade") or 0)

        # ============================
        # BLOQUEIO INTELIGENTE DE MOVIMENTAÇÃO DUPLICADA (USANDO MOVEMENTS)
        # ============================
        setor_destino_map = {
            "Ponto-01": "PTH",
            "Ponto-02": "SMT",
            "Ponto-03": "SMT",
            "Ponto-04": "IM",
            "Ponto-05": "PA",
            "Ponto-06": "IM",
            "Ponto-07": "ESTOQUE"
        }
        setor_destino = setor_destino_map.get(ponto)

        # Checa se já existe um movement registrado para esta label/ponto/acao
        already = conn.execute(
            "SELECT 1 FROM movements WHERE label_id=? AND ponto=? AND acao=? LIMIT 1",
            (label.get("id"), ponto, acao)
        ).fetchone()

        if already:
            # já teve movimento idêntico — bloqueia
            conn.close()
            flash("Esta etiqueta já foi registrada aqui. Movimentação duplicada não permitida.", "danger")
            return redirect(url_for("movimentar", p=ponto_url))

        # Opcional: proteção adicional para casos óbvios
        # (evita PRODUCTION sendo registrada como 'produção' em mesmo setor se não houver mudança alguma)
        if setor_destino == setor_origem:
            # se for PRODUCAO e nada foi produzido (remaining == capacidade) - normalmente é OK permitir,
            # por isso deixamos apenas um aviso (não bloqueamos), mas mantemos o bloqueio para RECEBIMENTO
            if acao == "RECEBIMENTO":
                conn.close()
                flash("Recebimento já registrado anteriormente.", "danger")
                return redirect(url_for("movimentar", p=ponto_url))
            # para PRODUCAO não bloqueamos aqui — controle por movements garante que não contabilize duas vezes



        # ============================================================== 
        # MODELOS SMT-FIRST
        # ============================================================== 
        if model["code"] in SMT_FIRST_MODELS:
            # Primeiro bip no SMT → registra produção local sem abater
            if ponto == "Ponto-02" and acao == "PRODUCAO":
                transfer = capacidade  # pega a capacidade total da etiqueta

                # Cria nova label DISPONÍVEL no SMT
                conn.execute("""
                    INSERT INTO labels
                    (model_id, lote, producao_total, capacidade_magazine, remaining,
                     created_at, linked_label_id, setor_atual, fase,
                     top_done, bottom_done)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    model["id"], label["lote"], transfer, capacidade, transfer,
                    datetime.now().isoformat(), label["id"], "SMT", "DISPONIVEL",
                    label.get("top_done"), label.get("bottom_done")
                ))

                new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                register_movement(conn, model["id"], new_id, ponto, acao, transfer, setor_origem, "SMT")
                conn.commit()
                conn.close()
                flash(f"Produção registrada no SMT ({transfer} un.)", "success")
                return redirect(url_for("movimentar", p=ponto_url))

            # RECEBIMENTO para PTH → abate SMT, cria label PTH
            if ponto == "Ponto-01" and acao == "RECEBIMENTO":
                transfer = capacidade
                novo_remaining = max(remaining - transfer, 0)
                conn.execute("UPDATE labels SET remaining=?, updated_at=? WHERE id=?",
                             (novo_remaining, datetime.now().isoformat(), label["id"]))

                conn.execute("""
                    INSERT INTO labels
                    (model_id, lote, producao_total, capacidade_magazine, remaining,
                     created_at, linked_label_id, setor_atual, fase,
                     top_done, bottom_done)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    model["id"], label["lote"], transfer, capacidade, transfer,
                    datetime.now().isoformat(), label["id"], "PTH", "AGUARDANDO",
                    label.get("top_done"), label.get("bottom_done")
                ))
                new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                register_movement(conn, model["id"], new_id, ponto, acao, transfer, "SMT", "PTH")
                conn.commit()
                conn.close()
                flash(f"Recebimento registrado do SMT → PTH ({transfer} un.)", "success")
                return redirect(url_for("movimentar", p=ponto_url))

        # ============================================================== 
        # FLUXO NORMAL (PTH → SMT) 
        # ============================================================== 
        if ponto == "Ponto-01" and acao == "PRODUCAO":
            transfer = quantidade if quantidade > 0 else remaining
            if transfer <= 0 or transfer > remaining:
                conn.close()
                flash("Quantidade inválida.", "danger")
                return redirect(url_for("movimentar", p=ponto_url))

            # Abate PTH e cria nova label DISPONÍVEL
            conn.execute("UPDATE labels SET remaining=?, updated_at=? WHERE id=?",
                         (remaining - transfer, datetime.now().isoformat(), label["id"]))

            conn.execute("""
                INSERT INTO labels
                (model_id, lote, producao_total, capacidade_magazine, remaining,
                 created_at, linked_label_id, setor_atual, fase)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                model["id"], label["lote"], transfer, transfer, transfer,
                datetime.now().isoformat(), label["id"], "PTH", "DISPONIVEL"
            ))
            new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            register_movement(conn, model["id"], new_id, ponto, acao, transfer, setor_origem, "PTH")
            conn.commit()
            conn.close()
            flash(f"Produção registrada ({transfer} un.)", "success")
            return redirect(url_for("movimentar", p=ponto_url))

        # RECEBIMENTO normal PTH → SMT
        if ponto == "Ponto-02" and acao == "RECEBIMENTO":
            transfer = capacidade
            novo_remaining = max(remaining - transfer, 0)
            conn.execute("UPDATE labels SET remaining=?, updated_at=? WHERE id=?",
                         (novo_remaining, datetime.now().isoformat(), label["id"]))

            conn.execute("""
                INSERT INTO labels
                (model_id, lote, producao_total, capacidade_magazine, remaining,
                 created_at, linked_label_id, setor_atual, fase,
                 top_done, bottom_done)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                model["id"], label["lote"], transfer, capacidade, transfer,
                datetime.now().isoformat(), label["id"], "SMT", "AGUARDANDO",
                label.get("top_done"), label.get("bottom_done")
            ))
            new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            register_movement(conn, model["id"], new_id, ponto, acao, transfer, setor_origem, "SMT")
            conn.commit()
            conn.close()
            flash(f"Recebimento registrado ({transfer} un.)", "success")
            return redirect(url_for("movimentar", p=ponto_url))

        # ============================================================== 
        # OUTROS PONTOS
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
        conn.execute("UPDATE labels SET remaining=?, updated_at=? WHERE id=?",
                     (novo_remaining, datetime.now().isoformat(), label["id"]))

        destino_map = {
            "Ponto-03": "SMT",
            "Ponto-04": "IM",
            "Ponto-05": "PA",
            "Ponto-06": "IM",
            "Ponto-07": "ESTOQUE"
        }
        setor_destino = destino_map.get(ponto, setor_origem)
        fase_nova = get_fase(ponto, acao)
        conn.execute("""
            INSERT INTO labels
            (model_id, lote, producao_total, capacidade_magazine, remaining,
             created_at, linked_label_id, setor_atual, fase,
             top_done, bottom_done)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            model["id"], label["lote"],
            transfer, transfer, transfer,
            datetime.now().isoformat(), label["id"],
            setor_destino, fase_nova,
            label.get("top_done"), label.get("bottom_done")
        ))
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        register_movement(conn, model["id"], new_id, ponto, acao, transfer, setor_origem, setor_destino)
        conn.commit()
        conn.close()
        flash(f"{acao} registrada ({transfer} un.)", "success")
        return redirect(url_for("movimentar", p=ponto_url))

    return render_template("movimentar.html", model=model, label=label, ponto=ponto_url, hide_top_menu=True, clean_display_code=clean_display_code)

def extract_real_code(raw):
    if not raw:
        return ""

    # Trocar caracteres errados
    cleaned = raw.replace("ç", ";").replace(";;", ";")
    cleaned = cleaned.replace("http", "").replace("https", "")
    cleaned = cleaned.replace("://", "").replace("/", "").replace(":", "")

    # Divide por ';'
    partes = cleaned.split(";")

    for p in reversed(partes):
        p = p.strip()
        if p:
            return p

    return cleaned.strip()

def clean_display_qr(raw):
    if not raw:
        return ""

    real = extract_real_code(raw)
    if real:
        return real

    # Limpeza básica, se nada for encontrado
    txt = raw.upper()
    txt = (txt.replace("HTTP", "")
               .replace("Ç", "")
               .replace("ç", "")
               .replace(";", "")
               .replace(":", "")
               .strip())
    return txt

@app.route("/dashboard")
def dashboard():
    conn = get_db()
    # Lista de todos os modelos
    models = conn.execute("SELECT * FROM models ORDER BY model_name").fetchall()
    models = [dict(m) for m in models]

    # Para cada modelo, consulta saldo por setor + fase (somente remaining > 0)
    dashboard_data = []
    for m in models:
        labels = conn.execute("""
            SELECT setor_atual, fase, SUM(remaining) AS saldo
            FROM labels
            WHERE model_id=? AND remaining > 0
            GROUP BY setor_atual, fase
        """, (m["id"],)).fetchall()

        saldo_setores = []
        for l in labels:
            setor = l["setor_atual"] or "SEM SETOR"
            fase_raw = (l["fase"] or "").strip().upper()
            saldo = int(l["saldo"] or 0)

            # Mapeamento de exibição mais amigável
            if fase_raw in ("AGUARDANDO_BOTTOM",):
                display_fase = "Top produzido → Aguardando Bottom"
                status = "AGUARDANDO"
            elif fase_raw in ("AGUARDANDO_CQ",):
                display_fase = "Aguardando Liberação CQ"
                status = "AGUARDANDO"
            elif fase_raw in ("DISPONIVEL",):
                display_fase = "Disponível (Liberado)"
                status = "DISPONIVEL"
            elif fase_raw in ("EXPEDIDO","EXPEDICAO"):
                display_fase = "Expedido"
                status = "EXPEDIDO"
            else:
                display_fase = fase_raw if fase_raw else "AGUARDANDO"
                status = "AGUARDANDO" if fase_raw in ("","AGUARDANDO") else "DISPONIVEL" if saldo>0 else "AGUARDANDO"

            saldo_setores.append({
                "setor": setor,
                "fase": display_fase,
                "saldo": saldo,
                "status": status
            })

        dashboard_data.append({
            "model": m,
            "saldo_setores": saldo_setores
        })
    conn.close()
    return render_template("dashboard.html", data=dashboard_data)

@app.route("/history/<int:id>")
def history(id):
    with get_db() as conn:
        model = conn.execute("SELECT * FROM models WHERE id=?", (id,)).fetchone()
    hist = conn.execute(
        "SELECT * FROM history WHERE model_id=? ORDER BY changed_at DESC LIMIT 10",
        (id,)
    ).fetchall()

    etiquetas = conn.execute("SELECT * FROM labels WHERE model_id=? ORDER BY created_at DESC", (id,)).fetchall()
    movements = conn.execute("SELECT * FROM movements WHERE model_id=? ORDER BY created_at DESC LIMIT 50", (id,)).fetchall()
    conn.close()

    if not model:
        abort(404)

    # 🔹 Função para formatar data no padrão brasileiro
    def format_datetime(value):
        if not value:
            return ""
        try:
            s = str(value).replace("T", " ").split(".")[0]
            dt = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
            return dt.strftime("%d/%m/%Y às %H:%M:%S")
        except Exception:
            return str(value)

    # 🔹 Aplica a formatação
    hist = [dict(h) for h in hist]
    for h in hist:
        h["changed_at_formatted"] = format_datetime(h["changed_at"])

    etiquetas = [dict(e) for e in etiquetas]
    for e in etiquetas:
        e["created_at_formatted"] = format_datetime(e["created_at"])

    movements = [dict(mv) for mv in movements]
    for mv in movements:
        mv["created_at_formatted"] = format_datetime(mv["created_at"])

    return render_template("history.html", model=model, history=hist, etiquetas=etiquetas, movements=movements)

@app.route("/etiqueta/<string:code>")
def etiqueta(code):
    conn = get_db()

    # 🔹 Se o código tiver parte de lote, separamos
    if "-" in code:
        base_code = code.split("-")[0]
        lote_sufixo = "-".join(code.split("-")[1:])
        # Reconstrói o formato original (ex: "08-504" → "08 / 504")
        lote_sufixo = lote_sufixo.replace("-", " / ")
    else:
        base_code = code
        lote_sufixo = None

    model_row = conn.execute("SELECT * FROM models WHERE code=?", (base_code,)).fetchone()
    conn.close()

    if not model_row:
        return f"<h3>❌ Etiqueta não encontrada para código '{base_code}'.</h3>", 404

    model = dict(model_row)

    # 🔹 Substitui o lote apenas visualmente, sem alterar o banco
    if lote_sufixo:
        model["lote"] = lote_sufixo

    # 🔹 Formata o campo de atualização
    def format_updated_at(value):
        if not value:
            return ""
        try:
            s = str(value).replace("T", " ")
            s_short = s.split(".")[0].split("+")[0].split("Z")[0].strip()
            dt = datetime.strptime(s_short, "%Y-%m-%d %H:%M:%S")
            return dt.strftime("%d/%m/%Y às %H:%M:%S")
        except Exception:
            try:
                dt2 = datetime.fromisoformat(str(value))
                return dt2.strftime("%d/%m/%Y às %H:%M:%S")
            except Exception:
                return str(value)

    model["updated_at_formatted"] = format_updated_at(model.get("updated_at"))

    return render_template("etiqueta_view.html", m=model)

@app.route("/labels/<int:model_id>")
def label_history(model_id):
    conn = get_db()
    model = conn.execute("SELECT * FROM models WHERE id=?", (model_id,)).fetchone()
    etiquetas = conn.execute(
        "SELECT * FROM labels WHERE model_id=? ORDER BY created_at DESC", (model_id,)
    ).fetchall()
    conn.close()
    if not model:
        abort(404)
    return render_template("labels_history.html", model=model, etiquetas=etiquetas)

@app.route("/delete_label/<int:id>", methods=["DELETE"])
def delete_label(id):
    conn = get_db()
    conn.execute("DELETE FROM labels WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return "", 204

@app.route("/print_label/<int:model_id>/<lote>")
def print_label(model_id, lote):
    conn = get_db()
    model = conn.execute("SELECT * FROM models WHERE id=?", (model_id,)).fetchone()
    conn.close()
    if not model:
        abort(404)

    # Limpa o formato do lote, caso venha com "-"
    lote = lote.replace('-', ' / ')
    
    # Renderiza o mesmo template usado para etiquetas
    return render_template("label.html", model=model, lotes=[lote])

@app.route("/etiqueta_visualizar/<string:code>/<string:lote>")
def etiqueta_visualizar(code, lote):
    conn = get_db()
    model_row = conn.execute("SELECT * FROM models WHERE code=?", (code,)).fetchone()
    conn.close()

    if not model_row:
        return "<h3>Etiqueta não encontrada.</h3>", 404

    model = dict(model_row)
    lote_formatado = lote.replace("-", " / ")

    return render_template("label.html", m=model, lotes=[lote_formatado])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
