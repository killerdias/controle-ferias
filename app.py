from flask import Flask, render_template, request, redirect, url_for, flash
from flask_wtf import FlaskForm, CSRFProtect
from wtforms import StringField, DateField, IntegerField, SubmitField
from wtforms.validators import DataRequired, Optional, NumberRange
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sua_chave_secreta_muito_segura_123456'
csrf = CSRFProtect(app)

# === FORMULÁRIOS ===
class ColaboradorForm(FlaskForm):
    nome = StringField('Nome', validators=[DataRequired()])
    data_admissao = DateField('Data de Admissão', validators=[DataRequired()], format='%Y-%m-%d')
    submit = SubmitField('Salvar')

class FeriasForm(FlaskForm):
    ano = IntegerField('Ano', validators=[DataRequired()])
    dias_pendentes = IntegerField('Dias Pendentes', validators=[Optional()])
    dias_tirados = IntegerField('Dias Tirados', validators=[Optional()])
    saldo = IntegerField('Saldo', validators=[Optional()])
    previsao = StringField('Previsão', validators=[Optional()])
    vendas = StringField('Vendas', validators=[Optional()])
    data_tirada = DateField('Data Tirada', validators=[Optional()], format='%Y-%m-%d')
    submit = SubmitField('Salvar')

class ConcederFolgasForm(FlaskForm):
    quantidade = IntegerField('Quantidade de Folgas', validators=[DataRequired(), NumberRange(min=1)])
    motivo = StringField('Motivo (opcional)', validators=[Optional()])
    submit = SubmitField('Conceder Folgas')

class MarcarFolgaForm(FlaskForm):
    data_folga = DateField('Data da Folga', validators=[DataRequired()], format='%Y-%m-%d')
    submit = SubmitField('Marcar Folga')

class EmptyForm(FlaskForm):
    submit = SubmitField('Enviar')

# === BANCO DE DADOS ===
def init_db():
    conn = sqlite3.connect('ferias.db')
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS colaboradores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            data_admissao DATE NOT NULL
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS ferias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            colaborador_id INTEGER NOT NULL,
            ano INTEGER NOT NULL,
            dias_pendentes INTEGER,
            dias_tirados INTEGER,
            saldo INTEGER,
            previsao TEXT,
            vendas TEXT,
            data_tirada DATE,
            FOREIGN KEY (colaborador_id) REFERENCES colaboradores (id)
        )
    ''')

    c.execute('DROP TABLE IF EXISTS folgas')

    c.execute('''
        CREATE TABLE IF NOT EXISTS folgas_disponiveis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            colaborador_id INTEGER NOT NULL,
            quantidade INTEGER NOT NULL DEFAULT 1,
            data_concessao DATE DEFAULT (DATE('now')),
            motivo TEXT,
            FOREIGN KEY (colaborador_id) REFERENCES colaboradores (id)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS folgas_tiradas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            colaborador_id INTEGER NOT NULL,
            data_folga DATE NOT NULL,
            status TEXT NOT NULL DEFAULT 'pendente' CHECK(status IN ('pendente', 'tirada')),
            FOREIGN KEY (colaborador_id) REFERENCES colaboradores (id)
        )
    ''')

    conn.commit()
    conn.close()

# === ROTAS ===
@app.route('/')
def inicio():
    conn = sqlite3.connect('ferias.db')
    c = conn.cursor()
    c.execute('SELECT * FROM colaboradores ORDER BY nome')
    colaboradores = c.fetchall()
    conn.close()
    return render_template('inicio.html', colaboradores=colaboradores)

@app.route('/adicionar_colaborador', methods=['GET', 'POST'])
def adicionar_colaborador():
    form = ColaboradorForm()
    if form.validate_on_submit():
        conn = sqlite3.connect('ferias.db')
        c = conn.cursor()
        c.execute('INSERT INTO colaboradores (nome, data_admissao) VALUES (?, ?)',
                  (form.nome.data, form.data_admissao.data))
        conn.commit()
        conn.close()
        flash(f'Colaborador {form.nome.data} adicionado com sucesso!', 'success')
        return redirect(url_for('inicio'))
    return render_template('adicionar_colaborador.html', form=form)

@app.route('/editar_colaborador/<int:col_id>', methods=['GET', 'POST'])
def editar_colaborador(col_id):
    conn = sqlite3.connect('ferias.db')
    c = conn.cursor()
    if request.method == 'POST':
        form = ColaboradorForm()
        if form.validate_on_submit():
            c.execute('UPDATE colaboradores SET nome = ?, data_admissao = ? WHERE id = ?',
                      (form.nome.data, form.data_admissao.data, col_id))
            conn.commit()
            conn.close()
            flash('Colaborador atualizado com sucesso!', 'success')
            return redirect(url_for('inicio'))
    else:
        c.execute('SELECT * FROM colaboradores WHERE id = ?', (col_id,))
        col = c.fetchone()
        if col is None:
            conn.close()
            flash('Colaborador não encontrado!', 'danger')
            return redirect(url_for('inicio'))
        form = ColaboradorForm(nome=col[1], data_admissao=datetime.strptime(col[2], '%Y-%m-%d').date())
    conn.close()
    return render_template('editar_colaborador.html', form=form, col_id=col_id)

@app.route('/excluir_colaborador/<int:col_id>', methods=['POST'])
def excluir_colaborador(col_id):
    form = EmptyForm()
    if form.validate_on_submit():
        conn = sqlite3.connect('ferias.db')
        c = conn.cursor()
        c.execute('DELETE FROM ferias WHERE colaborador_id = ?', (col_id,))
        c.execute('DELETE FROM folgas_disponiveis WHERE colaborador_id = ?', (col_id,))
        c.execute('DELETE FROM folgas_tiradas WHERE colaborador_id = ?', (col_id,))
        c.execute('DELETE FROM colaboradores WHERE id = ?', (col_id,))
        conn.commit()
        conn.close()
        flash('Colaborador excluído com sucesso!', 'success')
    return redirect(url_for('inicio'))

@app.route('/colaborador/<int:col_id>')
def detalhes_colaborador(col_id):
    conn = sqlite3.connect('ferias.db')
    c = conn.cursor()
    c.execute('SELECT * FROM colaboradores WHERE id = ?', (col_id,))
    colaborador = c.fetchone()
    if not colaborador:
        conn.close()
        flash('Colaborador não encontrado!', 'danger')
        return redirect(url_for('inicio'))

    c.execute('SELECT * FROM ferias WHERE colaborador_id = ? ORDER BY ano DESC', (col_id,))
    ferias_registros = c.fetchall()

    c.execute('SELECT * FROM folgas_disponiveis WHERE colaborador_id = ? ORDER BY data_concessao DESC', (col_id,))
    folgas_concedidas = c.fetchall()

    c.execute('SELECT * FROM folgas_tiradas WHERE colaborador_id = ? ORDER BY data_folga DESC', (col_id,))
    folgas_tiradas = c.fetchall()

    # Saldo de folgas
    c.execute('SELECT COALESCE(SUM(quantidade), 0) FROM folgas_disponiveis WHERE colaborador_id = ?', (col_id,))
    total_concedidas = c.fetchone()[0] or 0
    c.execute('SELECT COUNT(*) FROM folgas_tiradas WHERE colaborador_id = ? AND status = "tirada"', (col_id,))
    total_tiradas = c.fetchone()[0] or 0
    saldo_folgas = total_concedidas - total_tiradas

    # === SALDO TOTAL DE FÉRIAS ===
    c.execute('SELECT COALESCE(SUM(saldo), 0) FROM ferias WHERE colaborador_id = ?', (col_id,))
    saldo_ferias = c.fetchone()[0] or 0

    conn.close()

    form = EmptyForm()

    return render_template('colaborador.html',
                           colaborador=colaborador,
                           ferias_registros=ferias_registros,
                           folgas_concedidas=folgas_concedidas,
                           folgas_tiradas=folgas_tiradas,
                           saldo_folgas=saldo_folgas,
                           saldo_ferias=saldo_ferias,
                           form=form)

# === FÉRIAS ===
@app.route('/adicionar_ferias/<int:col_id>', methods=['GET', 'POST'])
def adicionar_ferias(col_id):
    form = FeriasForm()
    if form.validate_on_submit():
        conn = sqlite3.connect('ferias.db')
        c = conn.cursor()
        c.execute('''
            INSERT INTO ferias (colaborador_id, ano, dias_pendentes, dias_tirados, saldo, previsao, vendas, data_tirada)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (col_id, form.ano.data, form.dias_pendentes.data, form.dias_tirados.data,
              form.saldo.data, form.previsao.data, form.vendas.data, form.data_tirada.data))
        conn.commit()
        conn.close()
        flash('Registro de férias adicionado!', 'success')
        return redirect(url_for('detalhes_colaborador', col_id=col_id))
    return render_template('adicionar_ferias.html', form=form, col_id=col_id)

@app.route('/editar_ferias/<int:ferias_id>', methods=['GET', 'POST'])
def editar_ferias(ferias_id):
    conn = sqlite3.connect('ferias.db')
    c = conn.cursor()
    col_tuple = c.execute('SELECT colaborador_id FROM ferias WHERE id = ?', (ferias_id,)).fetchone()
    if col_tuple is None:
        conn.close()
        flash('Registro de férias não encontrado!', 'danger')
        return redirect(url_for('inicio'))
    col_id = col_tuple[0]
    if request.method == 'POST':
        form = FeriasForm()
        if form.validate_on_submit():
            c.execute('''
                UPDATE ferias SET ano = ?, dias_pendentes = ?, dias_tirados = ?, saldo = ?,
                previsao = ?, vendas = ?, data_tirada = ? WHERE id = ?
            ''', (form.ano.data, form.dias_pendentes.data, form.dias_tirados.data,
                  form.saldo.data, form.previsao.data, form.vendas.data, form.data_tirada.data, ferias_id))
            conn.commit()
            conn.close()
            flash('Férias atualizadas!', 'success')
            return redirect(url_for('detalhes_colaborador', col_id=col_id))
    else:
        c.execute('SELECT * FROM ferias WHERE id = ?', (ferias_id,))
        f = c.fetchone()
        form = FeriasForm(
            ano=f[2], dias_pendentes=f[3], dias_tirados=f[4], saldo=f[5],
            previsao=f[6], vendas=f[7],
            data_tirada=datetime.strptime(f[8], '%Y-%m-%d').date() if f[8] else None
        )
    conn.close()
    return render_template('editar_ferias.html', form=form, ferias_id=ferias_id, col_id=col_id)

@app.route('/excluir_ferias/<int:ferias_id>', methods=['POST'])
def excluir_ferias(ferias_id):
    form = EmptyForm()
    if form.validate_on_submit():
        conn = sqlite3.connect('ferias.db')
        c = conn.cursor()
        col_tuple = c.execute('SELECT colaborador_id FROM ferias WHERE id = ?', (ferias_id,)).fetchone()
        if col_tuple is None:
            conn.close()
            return redirect(url_for('inicio'))
        col_id = col_tuple[0]
        c.execute('DELETE FROM ferias WHERE id = ?', (ferias_id,))
        conn.commit()
        conn.close()
        flash('Registro de férias excluído!', 'success')
        return redirect(url_for('detalhes_colaborador', col_id=col_id))
    return redirect(url_for('inicio'))

# === FOLGAS ===
@app.route('/conceder_folgas/<int:col_id>', methods=['GET', 'POST'])
def conceder_folgas(col_id):
    form = ConcederFolgasForm()
    if form.validate_on_submit():
        conn = sqlite3.connect('ferias.db')
        c = conn.cursor()
        c.execute('INSERT INTO folgas_disponiveis (colaborador_id, quantidade, motivo) VALUES (?, ?, ?)',
                  (col_id, form.quantidade.data, form.motivo.data))
        conn.commit()
        conn.close()
        flash(f'{form.quantidade.data} folga(s) concedida(s) com sucesso!', 'success')
        return redirect(url_for('detalhes_colaborador', col_id=col_id))
    return render_template('conceder_folgas.html', form=form, col_id=col_id)

@app.route('/marcar_folga/<int:col_id>', methods=['GET', 'POST'])
def marcar_folga(col_id):
    conn = sqlite3.connect('ferias.db')
    c = conn.cursor()

    c.execute('SELECT COALESCE(SUM(quantidade), 0) FROM folgas_disponiveis WHERE colaborador_id = ?', (col_id,))
    total_concedidas = c.fetchone()[0] or 0
    c.execute('SELECT COUNT(*) FROM folgas_tiradas WHERE colaborador_id = ? AND status = "tirada"', (col_id,))
    total_tiradas = c.fetchone()[0] or 0
    saldo = total_concedidas - total_tiradas

    form = MarcarFolgaForm()
    if form.validate_on_submit():
        if saldo <= 0:
            flash('Não há folgas disponíveis para marcar!', 'danger')
            conn.close()
            return render_template('marcar_folga.html', form=form, col_id=col_id, saldo=saldo)

        c.execute('INSERT INTO folgas_tiradas (colaborador_id, data_folga, status) VALUES (?, ?, "pendente")',
                  (col_id, form.data_folga.data))
        conn.commit()
        conn.close()
        flash('Folga marcada como pendente!', 'success')
        return redirect(url_for('detalhes_colaborador', col_id=col_id))

    conn.close()
    return render_template('marcar_folga.html', form=form, col_id=col_id, saldo=saldo)

@app.route('/confirmar_folga/<int:folga_id>', methods=['POST'])
def confirmar_folga(folga_id):
    form = EmptyForm()
    if form.validate_on_submit():
        conn = sqlite3.connect('ferias.db')
        c = conn.cursor()
        c.execute('SELECT colaborador_id FROM folgas_tiradas WHERE id = ? AND status = "pendente"', (folga_id,))
        result = c.fetchone()
        if result:
            col_id = result[0]
            c.execute('UPDATE folgas_tiradas SET status = "tirada" WHERE id = ?', (folga_id,))
            conn.commit()
            flash('Folga confirmada como tirada!', 'success')
        else:
            flash('Folga não encontrada ou já confirmada.', 'danger')
        conn.close()
        return redirect(url_for('detalhes_colaborador', col_id=col_id))
    return redirect(url_for('inicio'))

# === RESUMO DE FOLGAS PARA WHATSAPP ===
@app.route('/resumo_folgas/<int:col_id>', methods=['GET', 'POST'])
def resumo_folgas(col_id):
    conn = sqlite3.connect('ferias.db')
    c = conn.cursor()
    c.execute('SELECT nome FROM colaboradores WHERE id = ?', (col_id,))
    nome_result = c.fetchone()
    if not nome_result:
        conn.close()
        flash('Colaborador não encontrado!', 'danger')
        return redirect(url_for('inicio'))
    nome = nome_result[0]

    # === TOTAL CONCEDIDAS ===
    c.execute('SELECT COALESCE(SUM(quantidade), 0) FROM folgas_disponiveis WHERE colaborador_id = ?', (col_id,))
    total_concedidas = c.fetchone()[0] or 0

    # === JÁ TIRADAS ===
    c.execute('SELECT data_folga FROM folgas_tiradas WHERE colaborador_id = ? AND status = "tirada" ORDER BY data_folga', (col_id,))
    tiradas = c.fetchall()
    qtd_tiradas = len(tiradas)

    # === SALDO ATUAL ===
    saldo = total_concedidas - qtd_tiradas

    # === PENDENTES (AGENDADAS) ===
    c.execute('SELECT data_folga FROM folgas_tiradas WHERE colaborador_id = ? AND status = "pendente" ORDER BY data_folga', (col_id,))
    agendadas = c.fetchall()
    qtd_agendadas = len(agendadas)

    conn.close()

    # === TEXTO WHATSAPP ===
    texto = f"*RESUMO DE FOLGAS - {nome.upper()}*\n\n"
    texto += f"*Total concedidas:* {total_concedidas} folga"
    if total_concedidas != 1: texto += "s"
    texto += "\n"

    if tiradas:
        texto += f"*Já tiradas:* {qtd_tiradas}\n"
        for data, in tiradas:
            dia, mes, ano = data.split('-')[2], data.split('-')[1], data.split('-')[0]
            texto += f"• {dia}/{mes}/{ano}\n"
    else:
        texto += "*Já tiradas:* Nenhuma\n"

    texto += f"\n*Saldo atual:* {saldo}\n"
    texto += f"*Agendadas:* {qtd_agendadas}\n"

    if agendadas:
        texto += "\n*Agendado para:*\n"
        for data, in agendadas:
            dia, mes, ano = data.split('-')[2], data.split('-')[1], data.split('-')[0]
            texto += f"• {dia}/{mes}/{ano}\n"
    else:
        texto += "\n*Agendado para:*\n• Nenhuma\n"

    return render_template('resumo_folgas.html',
                           col_id=col_id,
                           nome=nome,
                           total_concedidas=total_concedidas,
                           tiradas=tiradas,
                           qtd_tiradas=qtd_tiradas,
                           saldo=saldo,
                           qtd_agendadas=qtd_agendadas,
                           agendadas=agendadas,
                           texto_whatsapp=texto)

# === RESUMO DE FÉRIAS PARA WHATSAPP ===
@app.route('/resumo_ferias/<int:col_id>', methods=['GET', 'POST'])
def resumo_ferias(col_id):
    conn = sqlite3.connect('ferias.db')
    c = conn.cursor()
    c.execute('SELECT nome FROM colaboradores WHERE id = ?', (col_id,))
    nome_result = c.fetchone()
    if not nome_result:
        conn.close()
        flash('Colaborador não encontrado!', 'danger')
        return redirect(url_for('inicio'))
    nome = nome_result[0]

    c.execute('SELECT * FROM ferias WHERE colaborador_id = ? ORDER BY ano DESC', (col_id,))
    ferias = c.fetchall()

    conn.close()

    texto = f"*RESUMO DE FÉRIAS - {nome.upper()}*\n\n"
    if not ferias:
        texto += "Nenhum registro de férias."
    else:
        for f in ferias:
            ano = f[2]
            pendentes = f[3] if f[3] is not None else '-'
            tirados = f[4] if f[4] is not None else '-'
            saldo = f[5] if f[5] is not None else '-'
            previsao = f[6] if f[6] else '-'
            vendas = f[7] if f[7] else '-'
            data_tirada = f[8] if f[8] else '-'
            texto += f"*Ano: {ano}*\n"
            texto += f"Pendentes: {pendentes}\n"
            texto += f"Tirados: {tirados}\n"
            texto += f"Saldo: {saldo}\n"
            texto += f"Previsão: {previsao}\n"
            texto += f"Vendas: {vendas}\n"
            texto += f"Data Tirada: {data_tirada}\n\n"

    return render_template('resumo_ferias.html',
                           col_id=col_id,
                           nome=nome,
                           ferias=ferias,
                           texto_whatsapp=texto)

if __name__ == '__main__':
   # init_db()
      app.run()