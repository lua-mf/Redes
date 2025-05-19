import socket
from datetime import datetime
from time import sleep

def calcular_checksum(pacote):
    return sum(ord(char) for char in pacote) % 256

HOST = 'localhost'
PORT = 50000

def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((HOST, PORT))
    s.listen()
    print(f"Servidor esperando conexão do cliente em {HOST}:{PORT}...")

    try:
        while True:
            conn, ender = s.accept()
            processar_comunicacao(conn, ender)
            conn.close()
            print("Conexão encerrada com o cliente. Aguardando nova conexão...")
    except KeyboardInterrupt:
        print("\nServidor encerrado pelo usuário.")
    except Exception as e:
        print(f"Erro no servidor: {e}")
    finally:
        s.close()
        print("Servidor encerrado.")

def processar_comunicacao(conn, ender):
    print('Conectado em ', ender)
    
    try:
        print("\nAguardando handshake do cliente...")
        handshake = conn.recv(1024).decode()
        
        if not handshake:
            print("Cliente desconectou.")
            return
            
        print(f"Handshake recebido: {handshake}")
        
        partes = handshake.split(',')
        if len(partes) < 4:
            conn.sendall("nack_handshake".encode())
            print("Handshake inválido.")
            return

        try:
            modo_operacao = int(partes[0].split('=')[1])
            tamanho_max = int(partes[1].split('=')[1])
            modo_envio = int(partes[2].split('=')[1])
            qtd_pacotes = int(partes[3].split('=')[1])
            
            tamanho_janela = 1
            if len(partes) > 4 and partes[4].startswith("janela="):
                tamanho_janela = int(partes[4].split('=')[1])
        except (ValueError, IndexError):
            conn.sendall("nack_handshake".encode())
            print("Erro no parsing do handshake.")
            return

        print(f"Modo de operação: {'Go-Back-N' if modo_operacao == 1 else 'Repetição Seletiva'}")
        print(f"Tamanho máximo: {tamanho_max}, Modo de envio: {'Individual' if modo_envio == 1 else 'Lote'}")
        print(f"Quantidade de pacotes: {qtd_pacotes}, Tamanho da janela: {tamanho_janela}")
        conn.sendall("ack_handshake".encode())

        print("\nAguardando pacotes...\n")
        
        buffer_completo = ""
        pacotes_processados = 0
        mensagem_completa = ""
        
        # Para armazenar pacotes fora de ordem (para repetição seletiva)
        pacotes_armazenados = {}
        proximo_esperado = 1
        
        # Variáveis para controle de ACKs no Go-Back-N em lote
        ultimo_pacote_continuo = 0
        pacotes_recebidos_em_ordem = []
        
        # Para evitar NACK duplicados  
        nacks_enviados = set()
        acks_enviados = set()

        # Configuração de timeout mais generosa para lote
        if modo_envio == 2:
            conn.settimeout(30.0)  # 30 segundos para modo lote
        else:
            conn.settimeout(10.0)

        timeout_count = 0
        max_timeouts = 3

        while pacotes_processados < qtd_pacotes and timeout_count < max_timeouts:
            try:
                dados = conn.recv(1024).decode()
                
                if not dados:
                    print("Cliente desconectou durante a transmissão.")
                    return
                    
                print(f"[DEBUG] Dados recebidos: '{dados}' (tamanho: {len(dados)})")
                buffer_completo += dados
                timeout_count = 0  # Reset contador de timeout quando recebe dados
                
            except socket.timeout:
                timeout_count += 1
                print(f"[DEBUG] Timeout {timeout_count}/{max_timeouts} - Não há dados chegando")
                
                # Se estamos em modo lote Go-Back-N e temos pacotes para confirmar
                if modo_envio == 2 and modo_operacao == 1 and ultimo_pacote_continuo > 0:
                    if ultimo_pacote_continuo not in acks_enviados:
                        sleep(0.05)
                        conn.sendall(f"ack|{ultimo_pacote_continuo}".encode())
                        acks_enviados.add(ultimo_pacote_continuo)
                        print(f"[TIMEOUT ACK] ACK de lote enviado para pacote {ultimo_pacote_continuo}")
                        
                        if ultimo_pacote_continuo >= qtd_pacotes:
                            pacotes_processados = qtd_pacotes
                            break
                continue
            
            # Processa o buffer
            while '|' in buffer_completo and pacotes_processados < qtd_pacotes:
                print(f"[DEBUG] Processando buffer: '{buffer_completo[:50]}...'")
                
                primeiro_separador = buffer_completo.find('|')
                if primeiro_separador < 3:
                    print(f"[DEBUG] Primeiro separador em posição inválida: {primeiro_separador}")
                    buffer_completo = buffer_completo[1:]
                    continue
                    
                try:
                    checksum_recebido = int(buffer_completo[:primeiro_separador])
                except ValueError:
                    print(f"[DEBUG] Erro ao extrair checksum: '{buffer_completo[:primeiro_separador]}'")
                    buffer_completo = buffer_completo[primeiro_separador+1:]
                    continue
                    
                resto = buffer_completo[primeiro_separador+1:]
                segundo_separador = resto.find('|')
                if segundo_separador == -1:
                    print(f"[DEBUG] Segundo separador não encontrado em: '{resto[:20]}...'")
                    break
                    
                try:
                    numero_sequencia = int(resto[:segundo_separador])
                except ValueError:
                    print(f"[DEBUG] Erro ao extrair número de sequência: '{resto[:segundo_separador]}'")
                    buffer_completo = buffer_completo[primeiro_separador+1:]
                    continue
                    
                # Extrai o conteúdo corretamente
                inicio_conteudo = primeiro_separador + 1 + segundo_separador + 1
                resto_buffer = buffer_completo[inicio_conteudo:]
                
                # Para pacotes de 3 caracteres ou menos, pega tudo até o próximo pacote
                if len(resto_buffer) >= 3:
                    # Procura pelo início do próximo pacote (padrão: 3dígitos|3dígitos|)
                    proximo_pacote = -1
                    for i in range(3, len(resto_buffer)-6):
                        if (resto_buffer[i:i+1] in '0123456789' and 
                            resto_buffer[i+3:i+4] == '|' and
                            resto_buffer[i+7:i+8] == '|'):
                            proximo_pacote = i
                            break
                    
                    if proximo_pacote != -1:
                        conteudo_pacote = resto_buffer[:proximo_pacote]
                        buffer_completo = buffer_completo[inicio_conteudo + proximo_pacote:]
                    else:
                        # Não há próximo pacote, pega até o final (mas máximo 3 chars)
                        conteudo_pacote = resto_buffer[:3] if len(resto_buffer) >= 3 else resto_buffer
                        buffer_completo = resto_buffer[len(conteudo_pacote):]
                else:
                    conteudo_pacote = resto_buffer
                    buffer_completo = ""
                
                if not conteudo_pacote:
                    print(f"[DEBUG] Conteúdo vazio, continuando...")
                    break
                
                checksum_calculado = calcular_checksum(conteudo_pacote)
                horario = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                
                print(f"\n=== Pacote recebido ===")
                print(f"- Conteúdo: '{conteudo_pacote}'")
                print(f"- Número de sequência: {numero_sequencia}")
                print(f"- Tamanho: {len(conteudo_pacote)}")
                print(f"- Horário: {horario}")
                print(f"- Checksum recebido: {checksum_recebido}")
                print(f"- Checksum calculado: {checksum_calculado}")
                print(f"- Próximo esperado: {proximo_esperado}")
                
                if checksum_recebido == checksum_calculado:
                    print("- Status: Checksum OK!")
                    
                    if modo_operacao == 1:  # Go-Back-N
                        if numero_sequencia == proximo_esperado:
                            # Pacote em ordem - aceita
                            mensagem_completa += conteudo_pacote
                            pacotes_processados += 1
                            proximo_esperado += 1
                            ultimo_pacote_continuo = numero_sequencia
                            pacotes_recebidos_em_ordem.append(numero_sequencia)
                            
                            print(f"- ACEITO: Pacote {numero_sequencia} em ordem (total processados: {pacotes_processados})")
                            
                            if modo_envio == 1:  # Individual
                                sleep(0.05)
                                conn.sendall(f"ack|{numero_sequencia}".encode())
                                print(f"- ACK individual enviado para pacote {numero_sequencia}")
                            # Em modo lote, ACK será enviado em batches
                            
                        else:
                            # Pacote fora de ordem - DESCARTA em Go-Back-N
                            print(f"- DESCARTADO: Pacote {numero_sequencia} fora de ordem (esperava {proximo_esperado})")
                            
                            if modo_envio == 1:  # Individual
                                if ultimo_pacote_continuo > 0:
                                    sleep(0.05)
                                    conn.sendall(f"ack|{ultimo_pacote_continuo}".encode())
                                    print(f"- ACK reenviado para último pacote aceito {ultimo_pacote_continuo}")
                    
                    else:  # Repetição Seletiva
                        if numero_sequencia == proximo_esperado:
                            mensagem_completa += conteudo_pacote
                            pacotes_processados += 1
                            proximo_esperado += 1
                            
                            # Verifica se há pacotes armazenados que agora estão em sequência
                            while proximo_esperado in pacotes_armazenados:
                                mensagem_completa += pacotes_armazenados[proximo_esperado]
                                del pacotes_armazenados[proximo_esperado]
                                pacotes_processados += 1
                                proximo_esperado += 1
                            
                            sleep(0.05)
                            conn.sendall(f"ack|{numero_sequencia}".encode())
                            print(f"- ACK enviado para pacote {numero_sequencia}")
                        
                        else:
                            if numero_sequencia > proximo_esperado:
                                # Pacote futuro - armazena
                                pacotes_armazenados[numero_sequencia] = conteudo_pacote
                                print(f"- Pacote {numero_sequencia} armazenado (esperava {proximo_esperado})")
                                
                                sleep(0.05)
                                conn.sendall(f"ack|{numero_sequencia}".encode())
                                print(f"- ACK enviado para pacote {numero_sequencia} (fora de ordem)")
                            else:
                                # Pacote duplicado
                                print(f"- Pacote {numero_sequencia} duplicado")
                                sleep(0.05)
                                conn.sendall(f"ack|{numero_sequencia}".encode())
                                print(f"- ACK enviado para pacote {numero_sequencia} (duplicado)")
                
                else:
                    print("- Status: ERRO de Checksum (pacote corrompido!)")
                    
                    # Evita NACK duplicado
                    chave_nack = f"{numero_sequencia}_{checksum_recebido}"
                    if chave_nack not in nacks_enviados:
                        nacks_enviados.add(chave_nack)
                        
                        sleep(0.05)
                        conn.sendall(f"nack|{numero_sequencia}".encode())
                        print(f"- NACK enviado para pacote corrompido {numero_sequencia}")
                    else:
                        print(f"- NACK já enviado para pacote {numero_sequencia}")
                
                print("========================\n")
        
        # Finalização para modo lote
        if modo_envio == 2:
            if modo_operacao == 1 and ultimo_pacote_continuo > 0:
                # Envia ACK final se ainda não foi enviado
                if ultimo_pacote_continuo not in acks_enviados:
                    sleep(0.1)
                    conn.sendall(f"ack|{ultimo_pacote_continuo}".encode())
                    acks_enviados.add(ultimo_pacote_continuo)
                    print(f"[FINAL] ACK final enviado para pacote {ultimo_pacote_continuo}")
            
            # Envia confirmação de conclusão
            sleep(0.2)
            conn.sendall("todos_pacotes_recebidos".encode())
            print("[FINAL] Mensagem 'todos_pacotes_recebidos' enviada")
    
        print(f"\n=== RESULTADO FINAL ===")
        print(f"Pacotes processados: {pacotes_processados}/{qtd_pacotes}")
        print(f"Mensagem completa: '{mensagem_completa}'")
        print("=======================")
        
    except Exception as e:
        print(f"Erro ao processar comunicação: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()