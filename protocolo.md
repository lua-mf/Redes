# Protocolo de Aplicação

## Visão Geral

Este é o protocolo básico que define as regras de comunicação entre o **cliente** e o **servidor** para a aplicação de envio de pacotes. Ele abrange a definição de pacotes, handshake, controle de integridade e modos de operação.

A comunicação ocorre via sockets TCP, com controle de integridade dos pacotes utilizando checksum. O sistema pode operar em dois modos de envio:

- **Go-Back-N**
- **Repetição Seletiva** (ainda não implementado no cliente)

O cliente também pode escolher entre enviar pacotes individualmente ou em lotes.

## Handshake Inicial

Quando o cliente se conecta ao servidor, ele envia uma mensagem inicial (**handshake**) para estabelecer as configurações de operação. O servidor responde com uma confirmação do handshake.

### Mensagem de Handshake

A mensagem de handshake contém as seguintes informações formatadas como uma string de parâmetros separados por vírgula:

```python
modo=MOD_OPERACAO,tamanho=TAMANHO_MAX,envio=MOD_ENVIO,qtd_pacotes=QTD_PACOTES
```

- `modo`: Especifica o modo de operação (1 para Go-Back-N, 2 para Repetição Seletiva).
- `tamanho`: O tamanho máximo de cada pacote de dados.
- `envio`: O modo de envio (1 para individual, 2 para em lote).
- `qtd_pacotes`: Quantidade total de pacotes que o cliente enviará.

#### Exemplo de Handshake do Cliente

```python
modo=1,tamanho=3,envio=1,qtd_pacotes=5
```

### Resposta do Servidor ao Handshake

O servidor responde com uma mensagem de confirmação:

```python
handshake_ok
```

Caso o servidor não consiga interpretar a mensagem do handshake ou se ocorrer algum erro, ele poderá retornar uma mensagem de erro.

## Estrutura de Pacotes

Cada pacote enviado pelo cliente contém as seguintes informações:

- **Checksum** (3 dígitos): verifica a integridade do pacote.
- **Número de sequência** (3 dígitos): identifica a ordem do pacote.
- **Conteúdo do pacote**: a parte da mensagem que está sendo enviada.

### Formato do Pacote

```python
CHECKSUM|NUM_SEQ|CONTEUDO
```

Onde:

- `CHECKSUM`: valor calculado do checksum do conteúdo do pacote.
- `NUM_SEQ`: número de sequência do pacote.
- `CONTEUDO`: o conteúdo do pacote, com o tamanho definido por `tamanho_max`.

#### Exemplo de Pacote Enviado

```
123|001|ola
```

Neste exemplo:

- `123` é o checksum do conteúdo do pacote "ola".
- `001` é o número de sequência do pacote.
- `ola` é o conteúdo do pacote.

## Controle de Integridade

Cada pacote enviado pelo cliente possui um **checksum** que é verificado pelo servidor para garantir que os dados não foram corrompidos durante a transmissão. Se o checksum calculado no servidor coincidir com o checksum do pacote recebido, o pacote é considerado válido. Caso contrário, o servidor envia um **NACK** (negativo) indicando erro.

### Respostas do Servidor

- **ACK** (Acknowledge): confirma o recebimento e integridade do pacote.
- **NACK** (Negative Acknowledge): indica que o pacote está corrompido e precisa ser reenviado.

#### Formato da Resposta do Servidor

- Para **ACK**: `ack|NUM_SEQ`
- Para **NACK**: `nack|NUM_SEQ`

#### Exemplos de Respostas do Servidor

- **ACK** (pacote 1): `ack|1`
- **NACK** (pacote 2): `nack|2`

## Modos de Envio

O cliente pode escolher entre dois modos de envio: **individual** ou **em lote**.

### Modo Individual

No modo individual, cada pacote é enviado e o cliente aguarda o **ACK** ou **NACK** do servidor antes de enviar o próximo pacote. O cliente pode retransmitir um pacote caso o servidor responda com **NACK** ou se o tempo de espera (*timeout*) para o **ACK** expirar.

### Modo Lote

No modo lote (ainda não implementado), o cliente pode enviar todos os pacotes de uma vez sem aguardar o **ACK** de cada um. O servidor, por sua vez, envia um **ACK** coletivo após processar todos os pacotes.

## Simulação de Falhas de Integridade

Falhas de integridade podem ser simuladas no cliente, corrompendo pacotes antes de enviá-los. Para isso, o cliente pode ativar um modo de **corruptor de pacotes**, em que os pacotes são enviados com dados alterados ou checksum incorreto para simular um erro de transmissão.

## Temporizador de Retransmissão

O cliente utiliza um temporizador para cada pacote enviado. Se o cliente não receber uma resposta dentro de um tempo específico (por exemplo, 2 segundos), ele reenviará o pacote automaticamente. O temporizador é cancelado assim que o **ACK** ou **NACK** é recebido.

## Exemplo de Fluxo de Comunicação

1. **Cliente**: Envia o handshake para o servidor (com as configurações de operação).
2. **Servidor**: Responde com "handshake_ok".
3. **Cliente**: Envia pacotes segmentados da mensagem. Cada pacote contém:
   - Checksum
   - Número de sequência
   - Conteúdo
4. **Servidor**: Responde com **ACK** ou **NACK** dependendo da integridade do pacote.
5. **Cliente**: Em caso de **NACK**, retransmite o pacote correspondente.
6. **Cliente**: Quando todos os pacotes forem confirmados, o cliente finaliza a transmissão e o servidor reconstrói a mensagem completa.

---
