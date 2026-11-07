# Pacote de leitura sem plugin aninhado — LST-17867

## Decisão e autorização

Marvin determinou: “arranca fora o acoes, ele podemos disponibilizar em um novo
plugin depois separado desse, outro repo sei la”. Contrato desta correção:
retirar o complemento Ações da distribuição deste repositório, preservar sua
fonte para retomada separada e manter o Prometheus de leitura funcionando.
Esta decisão substitui a regra anterior de apenas esconder Ações da vitrine.
A publicação corretiva segue a autorização desta frente e os gates existentes.

## Evidência comprovada

Na conta gratuita de teste, pelo claude.ai no Chrome, o importador obteve
`c28e5545cc1fff34ee35eaa8649d2d0b0c60a20c` (1.8.3) e respondeu `failed_content`:
`marketplace_sync_multiple_manifests`, com o detalhe
`plugin.json must be at .claude-plugin/plugin.json at the plugin root; found nested: 'acoes/.claude-plugin/plugin.json'`.
Auto-sync estava desligado na repetição. A mensagem genérica não era recusa do
plano ou do navegador. Isso não comprova a disponibilidade de todos os recursos
do plugin no plano gratuito; comprova a causa desta rejeição do importador.

## Escopo e contratos

- Remover `acoes/` da principal publicada, inclusive os dois manifestos, scripts
  de escrita e duas skills. Preservar os arquivos no histórico e em arquivo local
  de fontes com testes e dependências locais, fora do pacote distribuído.
- Remover `tests/test_acoes.py`, mantendo em testes do pacote de leitura as
  garantias de recusa de escrita, ausência de importação de módulos de escrita,
  ausência desses scripts, catálogo único e versão no lugar correto.
- Acrescentar regressão estrutural que demonstre o manifesto aninhado na base e
  exija exatamente um manifesto Claude na raiz de cada plugin do catálogo.
- Remover do README a instrução de instalar Ações por este marketplace; registrar
  separação futura sem inventar repositório ou disponibilidade.
- Incrementar os manifestos do pacote de leitura para 1.8.4 e atualizar changelog.
- Preservar byte a byte `scripts/` e as nove `skills/`; preservar correções 1.8.2 e
  1.8.3 e o nome/source do catálogo. Nenhuma migração, acesso, credencial, cron ou
  política de dados nova. Não há impacto de volume/retenção de dados operacionais.

## Fora de escopo e alternativas

Não criar/publicar outro repositório agora; não instalar capacidades de escrita,
não mexer em dados de contas e não integrar o PR #17. Sua worktree permanece
preservada, mas a proposta de recolocar Ações aqui ficou incompatível com esta
decisão. Mover ambos os pacotes para subdiretórios ou gerar cópia de distribuição
resolveria o aninhamento com mais estrutura; Marvin escolheu retirar Ações.

## Aceite e estratégia de testes

1. RED: teste do inventário encontra dois manifestos na base 1.8.3.
2. GREEN: inventário contém somente `.claude-plugin/plugin.json`; as nove skills
   seguem válidas; testes de leitura e do verificador passam.
3. Comparação Git comprova scripts/skills idênticos à base. A queda do total de
   testes é explicada pela retirada dos testes de Ações, não ocultada.
4. Catálogo e manifestos 1.8.4 válidos; Guard e revisão de conformidade/segurança.
5. Depois do merge, pacote público conferido e nova tentativa no mesmo Chrome/
   conta gratuita. Aceite de sincronização depende da resposta do servidor e da
   lista do plugin, sem confundir sincronizar catálogo com instalar o plugin.

## Rollout e rollback

Worktree `lst-17867-plugin-isolado`, base remota 1.8.3/c28e554. Integrar por PR e
Cypher Guard. Disponibilizar ZIP de leitura atualizado a partir do SHA integrado.
Rollback exige novo PR/versionamento e não deve reintroduzir o manifesto aninhado;
se Ações voltar no futuro, deve ser outro pacote fora da raiz deste plugin.

## Riscos

Quem dependia do código de Ações neste repositório precisará da distribuição
separada futura; essa retirada foi escolhida pelo Marvin. Preservar fonte e testes
reduz o custo da retomada. Novos erros do importador serão tratados pela evidência
da resposta, sem prometer que o fim deste erro garante todos os passos seguintes.
