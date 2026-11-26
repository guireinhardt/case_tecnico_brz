-- Prevenção: mudanças no banco para que os problemas do diagnóstico não voltem.
-- PostgreSQL. Aplica-se sobre case-candidato/schema.sql.
--
-- Pré-requisito: a tabela pagamento atual tem eventos duplicados (o script
-- antigo somava cada linha). A constraint UNIQUE do passo 3 falharia sobre
-- esses dados. Por isso o passo 0 recarrega a tabela a partir da base limpa
-- gerada por `python -m limpeza` (saida/pagamentos.csv).

BEGIN;

-- 0. Recarga da tabela de pagamentos a partir da base limpa ---------------
TRUNCATE pagamento;


-- 1. Número do processo: uma forma só (P7) --------------------------------
-- CHAR(20) completa com espaços o que tiver menos de 20 caracteres, então um
-- número que perdeu zeros à esquerda era gravado sem erro. VARCHAR + CHECK
-- aceita apenas os 20 dígitos, sem máscara.
ALTER TABLE precatorio
    ALTER COLUMN numero_processo TYPE VARCHAR(20),
    ADD CONSTRAINT precatorio_numero_20_digitos
        CHECK (numero_processo ~ '^[0-9]{20}$');


-- 2. Data de apresentação e prazo derivado (P11, P16) ---------------------
-- A data é gravada já convertida para o dia em Brasília pelo importador
-- (ex.: '2025-04-03T01:00:00Z'::timestamptz AT TIME ZONE 'America/Sao_Paulo').
-- O prazo deixa de ser digitado ou calculado fora do banco: é uma coluna
-- gerada, com a regra constitucional em um só lugar.
ALTER TABLE precatorio
    ADD COLUMN apresentado_em DATE,
    ADD COLUMN prazo_pagamento DATE GENERATED ALWAYS AS (
        CASE
            WHEN apresentado_em <= make_date(EXTRACT(YEAR FROM apresentado_em)::int, 4, 2)
                THEN make_date(EXTRACT(YEAR FROM apresentado_em)::int + 1, 12, 31)
            ELSE make_date(EXTRACT(YEAR FROM apresentado_em)::int + 2, 12, 31)
        END
    ) STORED;


-- 3. Pagamento: idempotência por evento (P17, P18) ------------------------
-- evento_id passa a ser único: reprocessar o mesmo arquivo, ou receber o
-- mesmo evento em sete arquivos diários seguidos, não duplica nada.
-- atualizado_em guarda a versão, para que só uma versão mais nova substitua
-- a anterior (ver o upsert no fim do arquivo).
ALTER TABLE pagamento
    ADD COLUMN atualizado_em TIMESTAMPTZ NOT NULL,
    ADD CONSTRAINT pagamento_evento_unico UNIQUE (evento_id);

-- O PostgreSQL não cria índice para chave estrangeira sozinho; o total pago
-- por precatório agrupa por esta coluna.
CREATE INDEX pagamento_precatorio_idx ON pagamento (precatorio_id);


-- 4. Total pago derivado, nunca acumulado (P5) -----------------------------
-- O script antigo somava cada valor a um total guardado: qualquer
-- reprocessamento inflava o número. O total passa a ser sempre calculado
-- dos eventos; estorno subtrai.
CREATE VIEW precatorio_total_pago AS
SELECT
    p.id AS precatorio_id,
    p.numero_processo,
    p.valor_face,
    COALESCE(SUM(CASE pg.tipo WHEN 'estorno' THEN -pg.valor ELSE pg.valor END), 0)
        AS total_pago
FROM precatorio p
LEFT JOIN pagamento pg ON pg.precatorio_id = p.id
GROUP BY p.id, p.numero_processo, p.valor_face;


-- 5. Rastreabilidade: lote e ocorrências (fim do descarte silencioso) -----
-- Cada arquivo importado vira um lote, identificado pelo hash do conteúdo.
-- A conta "lidos = aceitos + descartados + em dúvida" é garantida pelo banco.
CREATE TABLE lote_importacao (
    id              BIGSERIAL PRIMARY KEY,
    arquivo         TEXT        NOT NULL,
    sha256          CHAR(64)    NOT NULL UNIQUE,  -- o mesmo arquivo não entra duas vezes
    importado_em    TIMESTAMPTZ NOT NULL DEFAULT now(),
    registros_lidos INT         NOT NULL,
    aceitos         INT         NOT NULL,
    descartados     INT         NOT NULL,
    em_duvida       INT         NOT NULL,
    CONSTRAINT lote_conservacao
        CHECK (registros_lidos = aceitos + descartados + em_duvida)
);

ALTER TABLE pagamento
    ADD COLUMN lote_id BIGINT REFERENCES lote_importacao (id);

-- Todo registro que não virou pagamento fica aqui, com o motivo e o conteúdo
-- bruto, até alguém resolver. Uma consulta simples mostra as pendências:
--   SELECT * FROM ocorrencia_importacao WHERE resolvido_em IS NULL;
CREATE TABLE ocorrencia_importacao (
    id           BIGSERIAL   PRIMARY KEY,
    lote_id      BIGINT      NOT NULL REFERENCES lote_importacao (id),
    origem       TEXT        NOT NULL,  -- arquivo:linha
    destino      TEXT        NOT NULL CHECK (destino IN ('descartado', 'em dúvida')),
    motivo       TEXT        NOT NULL,
    conteudo     JSONB       NOT NULL,
    resolvido_em TIMESTAMPTZ
);

COMMIT;


-- Upsert usado pelo importador (exemplo) ------------------------------------
-- Insere o evento; se ele já existe, só substitui quando a versão recebida
-- é mais nova. Cópia idêntica ou versão antiga não altera nada.
--
-- INSERT INTO pagamento (precatorio_id, evento_id, tipo, valor, pago_em,
--                        atualizado_em, lote_id)
-- VALUES ($1, $2, $3, $4, $5, $6, $7)
-- ON CONFLICT (evento_id) DO UPDATE SET
--     precatorio_id = EXCLUDED.precatorio_id,
--     tipo          = EXCLUDED.tipo,
--     valor         = EXCLUDED.valor,
--     pago_em       = EXCLUDED.pago_em,
--     atualizado_em = EXCLUDED.atualizado_em,
--     lote_id       = EXCLUDED.lote_id
-- WHERE pagamento.atualizado_em < EXCLUDED.atualizado_em;
--
-- O lote inteiro roda numa transação: se a importação falhar no meio, nada
-- é gravado, e rodar de novo o mesmo arquivo é seguro.
