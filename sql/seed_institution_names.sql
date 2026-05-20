-- Fill placeholder institution names so the dashboard anchor selector
-- shows "MidFirst Bank" instead of "CERT 4063".
--
-- Run once (idempotent): set -a && source .env.local && set +a
-- uv run --with pg8000 python -c "import os,pg8000.dbapi,urllib.parse as u; \
--   url=u.urlparse(os.environ['DATABASE_URL']); c=pg8000.dbapi.connect( \
--   user=u.unquote(url.username),password=u.unquote(url.password), \
--   host=url.hostname,port=url.port or 5432,database=url.path.lstrip('/'), \
--   ssl_context=True); cur=c.cursor(); \
--   cur.execute(open('sql/seed_institution_names.sql').read()); c.commit()"

UPDATE institutions SET name = 'MidFirst Bank',               charter = 'NA' WHERE cert = 4063;
UPDATE institutions SET name = 'BOK Financial NA',            charter = 'NA' WHERE cert = 4214;
UPDATE institutions SET name = 'Bank OZK',                    charter = 'NM' WHERE cert = 110;
UPDATE institutions SET name = 'First-Citizens Bank & Trust', charter = 'SM' WHERE cert = 11063;
UPDATE institutions SET name = 'Frost Bank',                  charter = 'NM' WHERE cert = 5510;
