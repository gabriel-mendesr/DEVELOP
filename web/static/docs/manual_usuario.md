# Manual de Uso — Hotel Santos

**Versão:** 1.0  
**Público-alvo:** Usuários do sistema de gestão hoteleira  

---

## Sumário

1. [Acesso ao sistema](#1-acesso-ao-sistema)
2. [Tela inicial](#2-tela-inicial)
3. [Dashboard](#3-dashboard)
4. [Hóspedes](#4-hóspedes)
5. [Financeiro](#5-financeiro)
6. [Compras](#6-compras)
7. [Relatórios](#7-relatórios)
8. [Ajustes](#8-ajustes)
9. [Permissões de acesso](#9-permissões-de-acesso)

---

## 1. Acesso ao sistema

### Login

Acesse o sistema pelo navegador. Na tela de login, informe:

- **Usuário** — nome de usuário fornecido pelo administrador
- **Senha** — senha pessoal (mínimo 8 caracteres)

Clique em **Entrar**. Em caso de múltiplas tentativas incorretas, o sistema bloqueia o login por 1 minuto.

### Logout

Clique no ícone de saída no menu lateral para encerrar a sessão. Por segurança, sempre faça logout ao terminar o uso, especialmente em computadores compartilhados.

---

## 2. Tela inicial

Após o login, a tela inicial exibe cartões de atalho para cada módulo ao qual o usuário tem acesso. Clique em qualquer cartão para navegar diretamente ao módulo correspondente.

O menu lateral (sidebar) fica sempre disponível para navegação entre os módulos.

---

## 3. Dashboard

> **Permissão necessária:** Acesso ao Dashboard

O Dashboard oferece uma visão executiva dos dados financeiros e de hospedagem.

### Indicadores exibidos

| Indicador | Descrição |
|-----------|-----------|
| Total de hóspedes | Quantidade de hóspedes ativos no sistema |
| Saldo total | Soma dos saldos de todos os hóspedes |
| Vencidos | Valor total de hóspedes com crédito expirado |
| Vencendo em breve | Valor de créditos próximos ao vencimento |
| Total de multas | Soma de todas as multas em aberto |

### Gráficos

- **Entradas x Saídas mensais** — Gráfico de barras comparando créditos e débitos dos últimos 6 meses.
- **Hóspedes com vencimento próximo** — Lista dos hóspedes cujo crédito expira em breve.
- **Últimas movimentações** — As 10 transações mais recentes registradas no sistema.

---

## 4. Hóspedes

> **Permissão necessária:** Acesso a Hóspedes

Este módulo concentra o cadastro e o histórico financeiro de cada hóspede.

### 4.1 Lista de hóspedes

A tela principal exibe todos os hóspedes cadastrados. Recursos disponíveis:

- **Busca** — Pesquise por nome ou número de documento.
- **Filtros:**
  - *Todos* — exibe todos os hóspedes
  - *Vencidos* — hóspedes com crédito expirado
  - *Vencendo em breve* — hóspedes próximos ao vencimento
  - *Com multa* — hóspedes que possuem multas em aberto

### 4.2 Cadastrar novo hóspede

Clique em **Novo Hóspede** e preencha o formulário:

| Campo | Obrigatório | Descrição |
|-------|-------------|-----------|
| Nome | Sim | Nome completo do hóspede |
| Documento | Sim | CPF ou outro documento (usado como identificador único) |
| Telefone | Não | Número para contato via WhatsApp |
| E-mail | Não | Endereço de e-mail |

Após salvar, o hóspede aparece na lista e pode receber movimentações.

### 4.3 Ficha do hóspede

Clique sobre um hóspede na lista para abrir a ficha completa. A ficha contém:

#### Informações cadastrais
Nome, documento, telefone, e-mail, data de cadastro e status (ativo/inativo).

#### Saldo
- Saldo atual disponível
- Data de vencimento do crédito
- Aviso visual caso o crédito esteja vencido ou próximo ao vencimento

#### Multas
- Total de multas em aberto
- Histórico de multas aplicadas e pagas

#### Histórico de movimentações
Tabela com todas as transações: data, tipo, valor, categoria, observação e usuário responsável.

#### Anotações
Campo de texto livre para registrar observações sobre o hóspede (visível apenas internamente).

### 4.4 Adicionar movimentação

Na ficha do hóspede, clique em **Nova Movimentação** e preencha:

| Campo | Descrição |
|-------|-----------|
| Tipo | CRÉDITO, DÉBITO, MULTA ou PAGAMENTO DE MULTA |
| Valor | Valor em reais |
| Categoria | Selecione a categoria (configurável em Ajustes) |
| Observação | Descrição opcional da movimentação |

### 4.5 Multas

- **Aplicar multa:** selecione tipo *MULTA* ao adicionar movimentação.
- **Registrar pagamento de multa:** selecione tipo *PAGAMENTO DE MULTA*.

### 4.6 Alterar data de vencimento

> **Permissão necessária:** Alterar datas

Na lista de movimentações, usuários com permissão podem editar a data de vencimento de um lançamento específico. Clique no ícone de edição ao lado da data e selecione a nova data.

### 4.7 Extrato em PDF

Clique em **Baixar Extrato** para gerar um PDF com o resumo financeiro completo do hóspede: dados cadastrais, saldo, multas e histórico de movimentações.

### 4.8 Enviar voucher por WhatsApp

Se o hóspede tiver telefone cadastrado, o botão **WhatsApp** ficará disponível. Ao clicar, abre o WhatsApp com uma mensagem pré-formatada contendo o extrato do hóspede.

### 4.9 Exportar lista de hóspedes

Na tela de lista de hóspedes, utilize o botão **Exportar CSV** para baixar todos os hóspedes em formato de planilha com: Nome, Documento, Saldo, Vencimento e Status.

### 4.10 Ações administrativas

> **Permissão necessária:** Administrador

| Ação | Descrição |
|------|-----------|
| Inativar hóspede | Oculta o hóspede das listagens, mas preserva todo o histórico |
| Reativar hóspede | Reativa um hóspede previamente inativado |
| Excluir hóspede | Remove permanentemente o hóspede e todo o seu histórico — esta ação não pode ser desfeita |

---

## 5. Financeiro

> **Permissão necessária:** Acesso ao Financeiro

Exibe o histórico completo de movimentações de todos os hóspedes em uma única tela.

### Filtros disponíveis

| Filtro | Descrição |
|--------|-----------|
| Hóspede | Busca por nome ou documento |
| Tipo | CRÉDITO, DÉBITO, MULTA, PAGAMENTO DE MULTA |
| Data inicial / Data final | Período de exibição |

### Informações exibidas

Cada linha da tabela mostra: data, hóspede, documento, tipo de movimentação, valor, categoria, observação e usuário que registrou.

O sistema exibe até 500 movimentações mais recentes para o filtro aplicado.

### Exportar

- **CSV** — Exporta as movimentações do período selecionado em formato de planilha.
- **PDF** — Gera relatório mensal (disponível na tela de Relatórios).

---

## 6. Compras

> **Permissão necessária:** Acesso a Compras

Gerencie listas de compras com controle de itens, preços e histórico.

### 6.1 Lista de compras

A tela principal exibe todas as listas criadas (abertas e fechadas) com: data de criação, criador, status, quantidade de itens e custo total.

### 6.2 Criar nova lista

Clique em **Nova Lista** para criar uma lista com status *Aberta*. Você será redirecionado automaticamente para a tela de detalhes.

### 6.3 Gerenciar itens de uma lista

Clique sobre uma lista para abrir os detalhes. Em listas com status **Aberta**:

#### Adicionar item

Preencha o formulário:

| Campo | Descrição |
|-------|-----------|
| Data | Data da compra (DD/MM/AAAA) |
| Produto | Selecione um produto pré-cadastrado ou digite um nome personalizado |
| Quantidade | Quantidade adquirida |
| Valor unitário | Preço por unidade |

O sistema exibe o **histórico de preços** do produto selecionado para facilitar a comparação com compras anteriores.

#### Remover item

Clique no ícone de exclusão ao lado do item desejado. Disponível apenas em listas abertas.

### 6.4 Fechar lista

Quando todas as compras forem registradas, clique em **Fechar Lista**. Listas fechadas não permitem adição ou remoção de itens, servindo como registro histórico.

### 6.5 Total da lista

O custo total da lista é calculado automaticamente com base nos itens adicionados (quantidade × valor unitário).

---

## 7. Relatórios

> **Permissão necessária:** Acesso a Relatórios

Central de relatórios com três seções principais.

### 7.1 Inadimplentes

Exibe a lista de hóspedes com multas em aberto. O botão **Baixar PDF** gera o relatório de inadimplência formatado para impressão.

### 7.2 Extrato por hóspede

Busque um hóspede pelo número de documento para visualizar ou baixar o extrato financeiro completo. O PDF gerado inclui dados cadastrais, saldo atual, multas e histórico de movimentações.

### 7.3 Resumo mensal

Selecione o mês e ano desejados (formato MM/AAAA) para visualizar todas as movimentações do período.

Opções de exportação:
- **PDF** — Relatório formatado com totais e detalhamento
- **CSV** — Planilha com todas as colunas: Data, Hóspede, Documento, Tipo, Valor, Categoria, Observação, Usuário

---

## 8. Ajustes

A tela de Ajustes está dividida em seções. Cada usuário vê apenas as seções às quais tem acesso.

### 8.1 Minha senha

Disponível para todos os usuários. Permite alterar a senha pessoal:

1. Informe a **senha atual**
2. Digite a **nova senha** (mínimo 8 caracteres)
3. Confirme a nova senha no campo de verificação
4. Clique em **Salvar**

### 8.2 Configurações gerais

> **Permissão necessária:** Administrador

| Configuração | Descrição |
|--------------|-----------|
| Validade (meses) | Número de meses até o crédito do hóspede expirar (1–120) |
| Alerta antecipado (dias) | Quantos dias antes do vencimento o sistema exibe aviso (1–365) |

### 8.3 Categorias

> **Permissão necessária:** Administrador

Gerencie as categorias usadas nas movimentações financeiras.

- **Adicionar:** Digite o nome da categoria e clique em Salvar.
- **Excluir:** Clique no ícone de exclusão ao lado da categoria. Categorias em uso não podem ser excluídas.

### 8.4 Produtos

> **Permissão necessária:** Administrador ou Gerenciar Produtos

Gerencie a lista de produtos pré-cadastrados usados nas listas de compras.

- **Adicionar:** Digite o nome do produto e clique em Salvar.
- **Excluir:** Clique no ícone de exclusão ao lado do produto.

### 8.5 Usuários

> **Permissão necessária:** Administrador

#### Criar usuário

Clique em **Novo Usuário** e preencha:

| Campo | Descrição |
|-------|-----------|
| Nome de usuário | Identificador único para login |
| Senha | Senha inicial (o usuário pode alterar depois) |
| Permissões | Marque as permissões conforme a função do usuário |

#### Editar usuário

Clique em **Editar** ao lado do usuário para modificar permissões ou redefinir senha.

#### Excluir usuário

Clique em **Excluir** para remover o usuário. Não é possível excluir a própria conta.

#### Permissões disponíveis

| Permissão | Descrição |
|-----------|-----------|
| Administrador | Acesso total ao sistema |
| Acesso a Hóspedes | Ver e gerenciar hóspedes |
| Acesso ao Financeiro | Ver histórico de movimentações |
| Acesso a Compras | Gerenciar listas de compras |
| Acesso ao Dashboard | Ver indicadores e gráficos |
| Acesso a Relatórios | Gerar e baixar relatórios |
| Acesso ao Treinamento | Usar o simulador de treinamento |
| Alterar datas | Modificar datas de vencimento de movimentações |
| Gerenciar produtos | Adicionar e remover produtos das listas de compras |

### 8.6 Funcionários

> **Permissão necessária:** Administrador

Cadastre os funcionários do hotel para uso no módulo de Agenda.

- **Adicionar:** Digite o nome e clique em Salvar.
- **Escala padrão:** Configure os turnos habituais de cada funcionário (manhã, tarde, noite) para cada dia da semana.
- **Remover:** Clique no ícone de exclusão ao lado do funcionário.

### 8.7 Banco de dados

> **Permissão necessária:** Administrador

| Ação | Descrição |
|------|-----------|
| Backup | Gera um arquivo de backup do banco de dados |
| Otimizar | Executa manutenção no banco de dados para melhorar o desempenho |
| Excluir hóspede | Remove um hóspede pelo número de documento (ação permanente) |

### 8.8 Logs

> **Permissão necessária:** Administrador

Exibe o registro de auditoria com todas as ações realizadas no sistema: usuário, ação executada e data/hora.

O botão **Limpar logs** apaga todo o histórico de auditoria — use com cautela.

---

## 9. Permissões de acesso

A tabela abaixo resume quais permissões são necessárias para cada módulo:

| Módulo / Funcionalidade | Permissão necessária |
|-------------------------|----------------------|
| Tela inicial | Qualquer usuário logado |
| Dashboard | Acesso ao Dashboard |
| Hóspedes (visualizar/editar) | Acesso a Hóspedes |
| Hóspedes (inativar/excluir) | Administrador |
| Alterar data de vencimento | Alterar datas |
| Financeiro | Acesso ao Financeiro |
| Compras | Acesso a Compras |
| Gerenciar produtos | Administrador ou Gerenciar Produtos |
| Relatórios | Acesso a Relatórios |
| Minha Senha | Qualquer usuário logado |
| Configurações / Usuários / Funcionários / Banco de dados / Logs | Administrador |

---

*Para suporte ou dúvidas, entre em contato com o administrador do sistema.*
