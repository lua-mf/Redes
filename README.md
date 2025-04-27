# Projeto de Redes

Projeto da disciplina de Infraestrutura da Comunicação do 4° período na CESAR School.

## Objetivo

Aplicação cliente-servidor capaz de, na camada de aplicação, fornecer um transporte confiável de dados considerando um canal com perdas de dados e erros.

## Descrição do funcionamento da aplicação

O cliente deverá se conectar com o servidor e enviar comunicações de texto. Essas comunicações devem possuir um limite máximo de caracteres enviado por vez (definido no início da comunicação). As mensagens (pacotes da camada de aplicação) devem conter no máximo 3 caracteres como carga útil. Ao chegarem ao servidor, os metadados das mensagens individuais devem ser impressos e quando a comunicação estiver completa, ela deve ser apresentada corretamente no lado servidor da aplicação. Os metadados das confirmações enviadas pelo servidor devem ser apresentadas pelo cliente à medida que chegarem.

## Características específicas

- [ ] O cliente deve ser capaz de se conectar ao servidor através do localhost (quando na mesma máquina) ou via IP.
- [ ] A comunicação deve ocorrer **via sockets**;
- [ ] Um protocolo de aplicação (regras a nível de aplicação) deve ser proposto e descrito (requisições e respostas descritas);
- [ ] **A aplicação deve permitir que todas as características do transporte confiável de dados (ver tabela 3.1 do livro) sejam verificadas** (independentemente do protocolo da camada de transporte);
  - [x] **Soma de verificação**;
  - [ ] **Temporizador**;
  - [ ] **Número de sequência**;
  - [ ] **Reconhecimento**;
  - [ ] **Reconhecimento negativo**;
  - [ ] **Janela, paralelismo**.
- [ ] Falhas de integridade e/ou perdas de mensagens devem poder ser **simuladas**. Isto é, a nível de aplicação, deve ser possível inserir um ‘erro’ no lado cliente verificável pelo servidor;
- [ ] Deve ser possível enviar pacotes da camada de aplicação isolados a partir do cliente ou lotes com destino ao servidor. O servidor poderá ser configurado para confirmar a recepção individual dessas mensagens ou em grupo (i.e. deve aceitar as duas configurações);
- [ ] O código da aplicação bem como um relatório (incluindo o seu manual de utilização) devem ser apresentados e entregues no dia da apresentação
- [ ] **Pontuação extra**: todos os grupos que implementarem algum método de checagem de integridade receberão *0,5 pontos adicionais* na prova.

## Calendário de entregas

- [x] 07.04 - 15% - Aplicações cliente e servidor devem se conectar via socket e realizar o handshake inicial (trocando, pelo menos, modo de operação e tamanho máximo). (15%)
- [ ] 28.04 - 30% - Troca de mensagens entre cliente e servidor considerando um canal de comunicação erros e perdas não ocorrem.
- [ ] 19.05 - 25% - Inserção de erros e perdas simulados, bem como a implementação do correto comportamento dos processos. (25%)
- [ ] 28.05 - 30% - Entrega final.

---
