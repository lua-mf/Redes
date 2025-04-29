import socket
from datetime import datetime
from time import sleep

def calcular_checksum(pacote):
    return sum(ord(char) for char in pacote) % 256

HOST = 'localhost'
PORT = 50000

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind((HOST, PORT))
s.listen()
print(f"Servidor esperando conexão do cliente em {HOST}:{PORT}...")
conn, ender = s.accept()
print('Conectado em ', ender)

handshake = conn.recv(1024).decode()
print(f"Handshake recebido: {handshake}")

try:
    partes = handshake.split(',')
    if len(partes) < 4:
        conn.sendall("nack_handshake".encode())
        conn.close()
        print("Handshake inválido. Conexão encerrada.")
        exit()

    try:
        modo_operacao = int(partes[0].split('=')[1])
        tamanho_max = int(partes[1].split('=')[1])
        modo_envio = int(partes[2].split('=')[1])
        qtd_pacotes = int(partes[3].split('=')[1])
        tamanho_janela = int(partes[4].split('=')[1]) if len(partes) > 4 else 1
    except (ValueError, IndexError):
        conn.sendall("nack_handshake".encode())
        conn.close()
        print("Erro no parsing do handshake. Conexão encerrada.")
        exit()

    print(f"Modo: {'Go-Back-N' if modo_operacao == 1 else 'Repetição Seletiva'}, Envio: {'Individual' if modo_envio == 1 else 'Lote'}, Janela: {tamanho_janela}")
    conn.sendall("ack_handshake".encode())

    buffer_completo = ""
    mensagem_completa = ""
    base = 1  # Início da janela
    next_seq_expected = 1  # Próximo pacote que queremos
    pacotes_armazenados = {}

    pacotes_processados = 0

    while pacotes_processados < qtd_pacotes:
        dados = conn.recv(1024).decode()
        if not dados:
            break
        buffer_completo += dados

        while '|' in buffer_completo and pacotes_processados < qtd_pacotes:
            primeiro_sep = buffer_completo.find('|')
            if primeiro_sep < 1:
                break

            try:
                checksum_recebido = int(buffer_completo[:primeiro_sep])
            except ValueError:
                buffer_completo = buffer_completo[primeiro_sep+1:]
                continue

            resto = buffer_completo[primeiro_sep+1:]
            segundo_sep = resto.find('|')
            if segundo_sep == -1:
                break

            try:
                numero_sequencia = int(resto[:segundo_sep])
            except ValueError:
                buffer_completo = buffer_completo[primeiro_sep+1:]
                continue

            conteudo = resto[segundo_sep+1:]
            if len(conteudo) < 1:
                break

            if len(conteudo) <= 3:
                conteudo_pacote = conteudo
                buffer_completo = ""
            else:
                conteudo_pacote = conteudo[:3]
                buffer_completo = conteudo[3:]

            checksum_calculado = calcular_checksum(conteudo_pacote)
            horario = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            print(f"\nRecebido Pacote {numero_sequencia} às {horario}")

            if checksum_recebido == checksum_calculado:
                if modo_operacao == 1:  # Go-Back-N
                    if base <= numero_sequencia < base + tamanho_janela:
                        if numero_sequencia == next_seq_expected:
                            mensagem_completa += conteudo_pacote
                            pacotes_processados += 1
                            next_seq_expected += 1
                            base = next_seq_expected
                            conn.sendall(f"ack|{numero_sequencia}".encode())
                            print(f"- ACK enviado {numero_sequencia}")
                        else:
                            # Pacote dentro da janela mas fora da ordem -> ignora
                            conn.sendall(f"ack|{next_seq_expected-1}".encode())
                            print(f"- ACK reenviado {next_seq_expected-1} (esperava {next_seq_expected})")
                    else:
                        # Pacote fora da janela -> descarta
                        print(f"- Pacote {numero_sequencia} fora da janela, descartado.")
                else:  # Repetição Seletiva
                    if base <= numero_sequencia < base + tamanho_janela:
                        if numero_sequencia == next_seq_expected:
                            mensagem_completa += conteudo_pacote
                            pacotes_processados += 1
                            next_seq_expected += 1
                            # Verifica se pacotes armazenados podem ser liberados
                            while next_seq_expected in pacotes_armazenados:
                                mensagem_completa += pacotes_armazenados.pop(next_seq_expected)
                                pacotes_processados += 1
                                next_seq_expected += 1
                            base = next_seq_expected
                        else:
                            pacotes_armazenados[numero_sequencia] = conteudo_pacote
                        conn.sendall(f"ack|{numero_sequencia}".encode())
                        print(f"- ACK enviado {numero_sequencia}")
                    else:
                        print(f"- Pacote {numero_sequencia} fora da janela, descartado.")
            else:
                print(f"- ERRO de checksum no pacote {numero_sequencia}")
                conn.sendall(f"nack|{numero_sequencia}".encode())

    sleep(0.1)
    conn.sendall("todos_pacotes_recebidos".encode())
    print(f"\nMensagem reconstruída: '{mensagem_completa}'")

except Exception as e:
    print(f"Erro: {e}")
finally:
    conn.close()
    print("Conexão encerrada.")