# Projeto3

## FECAP - Fundação de Comércio Álvares Penteado

<p align="center">
  <a href="https://www.fecap.br/">
    <img src="https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRhZPrRa89Kma0ZZogxm0pi-tCn_TLKeHGVxywp-LXAFGR3B1DPouAJYHgKZGV0XTEf4AE&usqp=CAU" alt="FECAP - Fundação de Comércio Álvares Penteado" border="0">
  </a>
</p>

<h1 align="center">ASA · Agentes Inteligentes para o Sucesso do Estudante</h1>

<p align="center">
  Uma solução de agentes de IA para apoiar o acompanhamento acadêmico da Área do Sucesso Alvarista (ASA) da FECAP.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/status-em%20desenvolvimento-yellow" alt="Status">
  <img src="https://img.shields.io/badge/semestre-5º%20CC-blue" alt="Semestre">
  <img src="https://img.shields.io/badge/licença-CC%20BY--SA%204.0-lightgrey" alt="Licença">
</p>

---

## 📖 Sobre o projeto

A **Área do Sucesso Alvarista (ASA)** é o setor da FECAP responsável por acolher e acompanhar os estudantes ao longo da graduação, com foco em permanência e sucesso acadêmico.

**O problema.** O acompanhamento dos estudantes depende hoje de análise manual de dados espalhados em sistemas diferentes. Sinais de risco (queda de frequência, notas, pendências administrativas) chegam à equipe tarde demais para uma intervenção preventiva, e boa parte do tempo dos atendentes é consumida respondendo dúvidas repetitivas.

**A solução.** O ASA é uma plataforma **web** baseada em **agentes inteligentes** que lê os dados autorizados da instituição, transforma isso em sinais acionáveis para a equipe de atendimento e oferece orientação direta ao estudante. A arquitetura combina front-end web, API, serviços de IA e infraestrutura em nuvem, com **integração ao TOTVS** como fonte dos dados acadêmicos.

**O que o sistema entrega:**

| | |
|---|---|
| 🎯 **Para a equipe do ASA** | Priorização de casos, contexto consolidado do estudante e sugestões de encaminhamento. |
| 🎓 **Para o estudante** | Orientação sobre processos, prazos e pendências, disponível pelo navegador. |
| 🏛 **Para a instituição** | Visão agregada dos fatores que mais impactam permanência e evasão. |

**Três princípios inegociáveis:**

1. **Explicabilidade.** Todo sinal gerado pelo sistema vem acompanhado do porquê. Nada de caixa-preta.
2. **Privacidade.** Uso restrito a dados autorizados, com minimização e anonimização sempre que possível.
3. **Validação humana.** O agente sugere; quem decide é a equipe do ASA. O sistema nunca age sozinho sobre o estudante.

O projeto integra as disciplinas de **Inteligência Artificial**, **Programação Mobile**, **Álgebra Linear** e **Computação em Nuvem**.

---

## 🧰 Tecnologias

> Ajustar conforme o stack fechado pelo grupo.

| Camada | Ferramentas |
|---|---|
| Front-end web | *a definir* |
| Backend / API | *a definir* |
| IA / Dados | Python, Jupyter Notebooks |
| Integração | TOTVS (fonte dos dados acadêmicos) |
| Nuvem | *a definir* |
| Versionamento | Git e GitHub |

---

## 📂 Estrutura de pastas

```text
📁 Documentos
 ├── 📁 Entrega_1        # documentação da primeira entrega
 └── 📁 Entrega_2        # documentação da segunda entrega
📁 src
 ├── 📁 backend          # API, serviços e integração com o TOTVS
 ├── 📁 web              # aplicação web
 └── 📁 notebooks        # análise de dados e experimentos de IA
📄 .gitignore
📄 README.md
```

---

## ▶️ Como executar

> Preencher quando o ambiente estiver definido.

```bash
# clonar o repositório
git clone https://github.com/<organizacao>/<repositorio>.git
cd <repositorio>

# backend
cd src/backend
# instruções de instalação e execução

# web
cd ../web
# instruções de instalação e execução
```

---

## 👥 Equipe · EriTech +

| Integrante | GitHub |
|---|---|
| Bruno Eduardo da Silva Pinho | [@Smug303](https://github.com/Smug303) |
| Eric Victor Bittu Silva | [@eric-bittu](https://github.com/eric-bittu) |
| Vivian Kaori Umaki | [@vivikari](https://github.com/vivikari) |
| Yanko Lee | [@Yanko-dev](https://github.com/Yanko-dev) |

### Orientação

**Professor orientador:** [Rafael Diogo Rossetti](https://www.linkedin.com/in/rafael-rossetti/)

**Orientadores complementares:** Marcelo de Moura Amorim · Marcos Minoru Nakatsugawa · [Rodnil da Silva Moreira Lisboa](https://www.linkedin.com/in/professorrodnil/) · Rodrigo da Rosa

---

## 📋 Licença

Este projeto está licenciado sob a [Creative Commons BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).

## 🎓 Referências

- [FECAP · Área do Sucesso Alvarista (ASA)](https://www.fecap.br/asa/)
