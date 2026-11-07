# Solução de problemas — conexão com o Mercado Livre

Procure o sintoma na primeira coluna. Se não estiver aqui, diga ao usuário que não sabe e não
tente adivinhar — errar o diagnóstico custa mais que admitir.

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| `python3 pasta.py` para dizendo que a pasta sincroniza | a pasta está dentro de Dropbox, iCloud, Google Drive ou OneDrive | **não contorne.** Peça uma pasta fora do serviço de sincronização e comece ali. O token não pode ir para a nuvem sem o usuário saber |
| A mensagem diz explicitamente que o domínio não é permitido | `api.mercadolibre.com` não está nos domínios permitidos do Claude | Configurações → Capabilities → domínios permitidos. Em conta de empresa, só o administrador libera. Teste: o mesmo da etapa 2 da skill (uma linha de Python) — `curl` e `grep` não existem no Windows por padrão. **Qualquer `ok` serve, inclusive `ok 403`.** Falhou de outro jeito, veja a tabela de sinais da etapa 2 antes de concluir qualquer coisa |
| `Faltam valores em credenciais.txt` | arquivo não preenchido ou não salvo | `python3 meli.py check` mostra o que está vazio sem revelar valor. Peça para abrir, preencher e salvar |
| Erro de autorização citando `redirect_uri` | endereço diferente do cadastrado | a linha `MELI_REDIRECT_URI` precisa ser idêntica à do DevCenter, caractere por caractere |
| `O state nao confere` | a URL colada é de outra tentativa | rode `python3 autorizar.py` de novo e use a URL nova |
| `invalid_grant` na autorização | o código expirou (vale poucos minutos) ou já foi usado | refaça os dois passos da etapa 5, sem demora entre eles |
| `invalid_grant` depois de dias funcionando | refresh token expirou (6 meses sem uso), senha da conta mudou, Secret renovado, ou permissão revogada | atualize o `credenciais.txt` se o Secret mudou, e refaça a autorização |
| `invalid_operator_user_id` | autorizou com conta de operador ou colaborador | repita com a conta **administradora** da loja |
| `tokens.json sem refresh_token` | a aplicação não entregou acesso offline | veja "Acesso contínuo" em `devcenter.md` |
| Quer saber se a renovação funciona, sem esperar 6 horas | presença de refresh não é prova | `python3 meli.py renovar` — responde `renovacao funcionou` ou diz o que o ML recusou |
| `Outra execucao esta renovando a credencial nesta pasta` | duas coisas rodando ao mesmo tempo na mesma pasta (rotina agendada + uso manual, ou duas janelas) | **não é erro de conexão.** Espere a outra terminar e rode de novo. A trava existe justamente para a renovação não acontecer duas vezes |
| `Nao consigo gravar na pasta da conexao` | a pasta não aceita gravação (permissão, caminho, disco) | o pacote **não renovou de propósito**: renovar sem poder guardar o resultado derrubaria o acesso. Conserte a permissão da pasta e rode de novo |
| `403 PA_UNAUTHORIZED_RESULT_FROM_POLICIES` | falta permissão funcional | marque as quatro no DevCenter e autorize de novo |
| `401` depois de semanas | acesso expirado | refaça a etapa 5 |
| `429` | muitas chamadas seguidas | espere alguns segundos. Numa sala com muita gente na mesma rede isso é esperado: siga o combinado de todo mundo na mesma tela, comando só no ok |
| A conexão cai algumas horas depois de funcionar | duas cópias usando a mesma credencial | o refresh token é de uso único. Não copie `tokens.json` para outra máquina nem rode a mesma credencial em dois lugares |
| Não consegue apagar `RETORNO.txt` | o ambiente só apaga com permissão do usuário | o `autorizar.py` esvazia o arquivo; avise que ele pode apagar quando quiser |
| `python3` não existe ou é versão antiga | Python não instalado, ou 3.8 e anterior | **etapa 0 da skill** — você instala, ela não digita. Pergunte antes, porque altera o PATH |
| Tudo funciona, mas o apelido em `meli.py me` não é a loja dele | autorizou a conta errada | refaça a etapa 5 logado na conta certa |
| Instalou e o comando continua dizendo que não existe (Windows) | o PATH novo não vale para terminal já aberto | **não é falha de instalação.** Etapa 0.3: procure pelo caminho absoluto em `%LOCALAPPDATA%\Programs\Python\Python312\python.exe` e use ele daqui em diante |
| A instalação para citando permissão de administrador, ou um bloqueio nomeado por política | a máquina é gerida pela empresa dela | depende do administrador. Modo demonstração (etapa 7), com a volta marcada. **Não** oriente a desligar proteção nem a trocar de canal |
| A instalação falha e a mensagem não diz por quê | **causa não determinada** | modo demonstração dizendo só "não deu para instalar aqui". **Não atribua ao TI sem prova** |
| A pessoa recusa a instalação | decisão dela | modo demonstração, sem insistir e sem repetir o pedido |
| `pasta.py` avisa que não conseguiu fechar a permissão de um arquivo | o sistema não aplica restrição de leitura por arquivo (acontece no Windows) | **não é erro e não bloqueia.** Os arquivos seguem só na máquina dela e o pacote não envia nada para fora; o que não dá para prometer é que outro usuário da mesma máquina não consiga abrir o arquivo. Diga isso com essas palavras |
| Erro de rede citando DNS, nome que não resolve ou host desconhecido | a máquina não achou o endereço | **não conclua bloqueio administrativo.** Confira se a internet está de pé e tente de novo. Etapa 2 da skill tem a tabela de sinais |
| Erro citando certificado | quase sempre proxy da empresa no meio do caminho | é conversa com o TI, **mas sobre o proxy** — não sobre liberar domínio no Claude |
| Demorou e parou (timeout) | rede lenta ou Mercado Livre fora do ar | tente uma vez mais antes de qualquer conclusão |
| `winget` não existe nesta máquina | Windows 10 mais antigo, LTSC ou sem a Loja | **não é erro dela.** Plano B da etapa 0.2: ela baixa de `python.org/downloads`, versão 3.12, marcando **"Add python.exe to PATH"** na primeira tela e usando **"Install Now"** (não pede senha de administrador). Windows em ARM precisa da linha **arm64**, não do botão grande |
| Instalou pelo site e o comando continua não existindo | a caixa "Add python.exe to PATH" não foi marcada | reabrir o instalador, escolher **Modify** e marcar. Ou use o caminho absoluto da etapa 0.3 |
| `atualizacao.py` diz que não achou a pasta de configuração do Claude | a pessoa está no **Codex**, não no Claude | não é erro dela e não tem conserto: atualização automática é só do Claude. No Codex a atualização é manual — `codex plugin marketplace upgrade`. Diga isso e siga |
| `atualizacao.py` diz "O pacote prometheus não está instalado" e ela jura que está | versão 1.8.1 ou anterior: o script só olhava o registro do terminal | peça para ela atualizar o pacote. Da 1.8.2 em diante ele reconhece a instalação pelo aplicativo. **Não mande desinstalar** |

## Três coisas que não são erro

**O navegador mostra erro ao voltar da autorização.** É esperado, e é o desenho: o endereço
`.invalid` não existe de propósito, então o código fica só na barra de endereço do usuário.

**O painel vem vazio na primeira vez.** Nenhuma skill rodou ainda. Ele explica isso na tela.

**`HTTP 400` em um anúncio durante uma coleta.** Anúncio encerrado não responde consulta de
promoção. A skill pula, conta quantos pulou e segue.

## "Falha ao adicionar marketplace", ao colar o endereço do repositório

A máquina já tem esse catálogo registrado por outro formato de endereço — normalmente a
forma curta `sebemlabs-agents/prometheus`, gravada numa instalação anterior pelo terminal. O
Claude trata a URL inteira como fonte diferente e recusa, em vez de sobrescrever.

**O que fazer:** cole a forma curta `sebemlabs-agents/prometheus`. Se o catálogo já estiver
registrado, nem é preciso adicionar: o pacote aparece direto na aba **Descobrir**.

Para começar do zero: `claude plugin marketplace remove prometheus` desregistra o catálogo (e
desinstala os plugins vindos dele).


## Windows: `python3` não é reconhecido

No Windows o comando quase sempre é **`py -3`**, não `python3`. Digitar `python3` costuma
abrir a Loja da Microsoft em vez de rodar o Python. Teste `py -3 --version` e, se responder
3.8 ou mais novo, use `py -3` em todos os comandos.

Se nem `py -3` nem `python` responderem, instale do site oficial marcando **"Add python.exe
to PATH"** na primeira tela.

## Windows: a pasta Documentos é recusada

No Windows, `Documentos` normalmente está **dentro do OneDrive**, e o pacote recusa — como
deve. Use uma pasta na raiz do perfil, por exemplo `C:\Users\<nome>\prometheus`.

Não contorne a verificação: o token da conta não pode ir para a nuvem sem o dono saber.

## "Corrigiram isso, mas na minha máquina continua igual"

A atualização automática do catálogo está desligada — é o padrão para catálogo que não é da
Anthropic, não é defeito da máquina dela. Enquanto estiver assim, a pessoa fica na versão do
dia em que instalou, para sempre, sem nenhum aviso.

```
python3 atualizacao.py          # diz como está e em que versão ela está
python3 atualizacao.py --ligar  # liga, depois de perguntar a ela
```

**Rode você, não mande ela digitar.** Vale a partir da próxima vez que ela abrir o Claude.

Para trazer a versão nova agora, sem esperar: `claude plugin marketplace update prometheus` —
este é o único caso em que vale pedir que ela rode algo, e só se ela estiver com pressa.

### Se o script responder "quem controla é o aplicativo do Claude"

Ela instalou **pela tela**, não pelo terminal — vitrine da conta ou envio de `.zip`. Nesse
caminho não existe arquivo local para ligar: o botão fica em

> Configurações → Plugins → prometheus → **"Sincronizar automaticamente"**

Peça que ela ligue aí. O `--ligar` não serve e o script diz isso em vez de fingir que ligou.

**Pacote enviado por `.zip` não se atualiza de jeito nenhum**, nem com o botão: aquela cópia
fica parada na versão do arquivo. Depois do evento, ela troca pela instalação normal.
