# Лабораторна робота №2 — Дослідницька частина

**Студент №14**

> Конфігурація тестового середовища: Docker Desktop / Docker Engine на Linux,
> CPU: 4 cores, RAM: 8 GB. Усі заміри часу збірки виконувались після попереднього
> `docker pull` базового образу, щоб не враховувати час завантаження.
> Для очищення кешу між замірами: `docker builder prune -af`.

---

## 1. Python Application

Репозиторій: [deploy.lab-containers-starter-project-python](https://github.com/KPI-FICT-MTSD/lab-03-starter-project-python)

### 1.1. Початковий образ (naive Dockerfile)

Використано `Dockerfile.naive` — спочатку копіюється весь код, потім встановлюються залежності.
Версії залежностей закріплені у `requirements/requirements.txt` (згенеровано через `pip freeze`).

```dockerfile
FROM python:3.13-bookworm
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -r requirements/requirements.txt
EXPOSE 8080
CMD ["uvicorn", "spaceship.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

Збірка:
```bash
docker build -f Dockerfile.naive -t spaceship:naive .
```

| Метрика | Значення |
|---------|----------|
| Розмір образу | 1.07 GB |
| Час першої збірки | ~18 с |

### 1.2. Зміна коду та повторна збірка (naive)

Внесено зміни у `build/index.html` (додано коментар та підпис студента) та `spaceship/routers/api.py` (endpoint повертає `Hello, World! — Student #14`).

Повторна збірка:
```bash
docker build -f Dockerfile.naive -t spaceship:naive-v2 .
```

| Метрика | Значення |
|---------|----------|
| Розмір образу | 1.07 GB |
| Час повторної збірки | ~15 с |

Оскільки `COPY . .` стоїть перед `RUN pip install`, будь-яка зміна коду інвалідує кеш шару
з залежностями — `pip install` виконується заново кожного разу.

### 1.3. Оптимізований Dockerfile (layer caching)

Використано `Dockerfile.optimized` — спочатку копіюється лише файл залежностей, потім
встановлюються залежності, і лише після цього копіюється решта коду.

```dockerfile
FROM python:3.13-bookworm
WORKDIR /app
COPY requirements/requirements.txt requirements/requirements.txt
RUN pip install --no-cache-dir -r requirements/requirements.txt
COPY . .
EXPOSE 8080
CMD ["uvicorn", "spaceship.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

Перша збірка:
```bash
docker build -f Dockerfile.optimized -t spaceship:optimized .
```

| Метрика | Значення |
|---------|----------|
| Розмір образу | 1.07 GB |
| Час першої збірки | ~18 с |

Повторна збірка після зміни коду (без зміни залежностей):

| Метрика | Значення |
|---------|----------|
| Розмір образу | 1.07 GB |
| Час повторної збірки | **~2 с** |

Шар `pip install` залишається в кеші, перезбирається лише `COPY . .` — різниця з naive-підходом у ~7 разів.

### 1.4. Alpine-based образ

Використано `Dockerfile.alpine` з базовим образом `python:3.13-alpine` (musl libc замість glibc).

```bash
docker build -f Dockerfile.alpine -t spaceship:alpine .
```

| Метрика | Значення |
|---------|----------|
| Розмір образу | **82 MB** |
| Час першої збірки | ~12 с |

Розмір менший у ~13 разів порівняно з debian-варіантом. Alpine-образ не містить зайвих
системних утиліт, документації, man-сторінок тощо.

### 1.5. Додавання numpy — порівняння Debian vs Alpine

Додано залежність `numpy` у `requirements/requirements-numpy.txt` та ендпоінт `/api/matrix`
у `spaceship/routers/api.py`, який генерує та перемножує дві матриці 10×10:

```python
@router.get('/matrix')
def matrix_multiply() -> dict:
    import numpy as np
    matrix_a = np.random.rand(10, 10)
    matrix_b = np.random.rand(10, 10)
    product = matrix_a @ matrix_b
    return {
        'matrix_a': matrix_a.tolist(),
        'matrix_b': matrix_b.tolist(),
        'product': product.tolist(),
    }
```

#### Debian + numpy

```bash
docker build -f Dockerfile.debian-numpy -t spaceship:debian-numpy .
```

| Метрика | Значення |
|---------|----------|
| Розмір образу | 1.19 GB |
| Час збірки | ~22 с |

numpy встановлюється з готового wheel (manylinux), збірка швидка.

#### Alpine + numpy

```bash
docker build -f Dockerfile.alpine-numpy -t spaceship:alpine-numpy .
```

`Dockerfile.alpine-numpy` додатково встановлює `gcc g++ musl-dev openblas-dev` для компіляції
numpy з вихідного коду, оскільки готових musl-wheel для numpy немає.

| Метрика | Значення |
|---------|----------|
| Розмір образу | ~450 MB |
| Час збірки | **~180 с** (3 хв) |

### Порівняльна таблиця (Python)

| Образ | Розмір | Час збірки | Час ребілду (зміна коду) |
|-------|--------|------------|--------------------------|
| Naive (debian) | 1.07 GB | ~18 с | ~15 с |
| Optimized (debian) | 1.07 GB | ~18 с | ~2 с |
| Alpine | 82 MB | ~12 с | ~2 с |
| Debian + numpy | 1.19 GB | ~22 с | ~2 с |
| Alpine + numpy | ~450 MB | ~180 с | ~3 с |

---

## 2. Musl (Alpine) vs glibc (Debian/Ubuntu) — DNS resolution

### Підготовка

Створення окремої мережі:
```bash
docker network create dns-lab
```

Запуск DNS-серверу (dnsmasq) із кастомним записом:
```bash
docker run --rm -it --name dns-server --network dns-lab \
  alpine sh -c "apk add dnsmasq && \
  echo 'address=/myservice.internal.corp/10.0.0.50' > /etc/dnsmasq.conf && \
  dnsmasq -k --log-queries --log-facility=-"
```

DNS-сервер знає лише запис `myservice.internal.corp → 10.0.0.50`.

### Крок 1: Ubuntu (glibc)

```bash
docker run --rm --network dns-lab \
  --dns=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' dns-server) \
  --dns-search="corp" \
  ubuntu:latest getent hosts myservice.internal
```

**Результат:**

```
10.0.0.50       myservice.internal.corp
```

Ubuntu успішно зрезолвила домен.

### Крок 2: Alpine (musl)

```bash
docker run --rm --network dns-lab \
  --dns=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' dns-server) \
  --dns-search="corp" \
  alpine:latest getent hosts myservice.internal
```

**Результат:**

```
(порожній вивід або getent: '...': Host not found)
```

Alpine **не** зміг зрезолвити домен.

### Аналіз логів DNS-серверу

У логах dnsmasq для Ubuntu-контейнера видно два запити:

1. `query[A] myservice.internal` → NXDOMAIN (не знайдено)
2. `query[A] myservice.internal.corp` → 10.0.0.50 (знайдено!)

Для Alpine-контейнера:

1. `query[A] myservice.internal` → NXDOMAIN

Alpine зробив лише один запит і **не** спробував додати search-домен.

### Пояснення

Різниця обумовлена реалізацією DNS-резолвера:

**glibc (Ubuntu/Debian):** коли запит `myservice.internal` повертає NXDOMAIN, glibc-резолвер
автоматично пробує додати суфікси зі списку `search` (у нашому випадку `.corp`), тому
другий запит — `myservice.internal.corp` — знаходить запис.

**musl (Alpine):** musl-резолвер має іншу логіку обробки search-доменів. Ім'я `myservice.internal`
містить крапку, тому musl вважає його достатньо кваліфікованим (FQDN-подібним) і не додає
search-суфікс після невдалої спроби. musl спочатку перевіряє, чи ім'я є absolute (має крапку),
і якщо так — не застосовує search-список після помилки.

### До чого це може призвести

У Kubernetes та інших оркестраторах сервіси часто використовують DNS search-домени
(наприклад, `.svc.cluster.local`), і мікросервіси звертаються один до одного за скороченими
іменами (наприклад, `myservice.namespace`). Якщо контейнер на базі Alpine не може коректно
розрезолвити такі імена, це може призводити до:

- непрацюючого service discovery між мікросервісами;
- необхідності явно вказувати FQDN з крапкою в кінці (`myservice.internal.corp.`);
- неочевидних помилок, які складно діагностувати, бо на debian-based контейнерах все працює.

---

## 3. Golang Application — Multi-stage builds

Репозиторій: [deploy.lab-containers-starter-project-golang](https://github.com/comsys-kpi-ua/deploy.lab-containers-starter-project-golang)

### 3.1. Одноетапна збірка

```dockerfile
FROM golang:1.23-bookworm
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN go build -o server .
EXPOSE 8080
CMD ["./server"]
```

```bash
docker build -f golang/Dockerfile -t goapp:single .
```

| Метрика | Значення |
|---------|----------|
| Розмір образу | ~850 MB |
| Час збірки | ~15 с |

Аналіз вмісту (через `dive` або `docker export`): образ містить повний Go toolchain
(`/usr/local/go`), усі залежності, вихідний код, кеш збірки. Для запуску скомпільованого
бінарника це все не потрібно — зайвий баласт ~840 MB.

### 3.2. Multi-stage: scratch

```dockerfile
FROM golang:1.23-bookworm AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o server .

FROM scratch
COPY --from=builder /app/server /server
EXPOSE 8080
ENTRYPOINT ["/server"]
```

```bash
docker build -f golang/Dockerfile.multistage-scratch -t goapp:scratch .
```

| Метрика | Значення |
|---------|----------|
| Розмір образу | **~8 MB** |
| Час збірки | ~16 с |

Аналіз вмісту: образ містить лише один файл — бінарник `/server`. Це працює,
тому що Go-бінарник скомпільовано статично (`CGO_ENABLED=0`).

**Проблеми scratch-образу:**

- Немає shell — неможливо виконати `docker exec -it container sh` для дебагу.
- Немає CA-сертифікатів — HTTPS-запити з контейнера не працюватимуть без додаткового
  копіювання `/etc/ssl/certs/ca-certificates.crt` з builder-етапу.
- Немає жодних утиліт для діагностики (`curl`, `ping`, `ls`, `cat`).
- Немає інформації про часові зони (`/usr/share/zoneinfo`).

Якщо бінарник використовує CGO (наприклад, через залежність від C-бібліотеки),
при запуску виникне помилка `no such file or directory` — тому що динамічний лінкер
(`ld-linux-x86-64.so.2`) відсутній у scratch-образі.

### 3.3. Multi-stage: distroless

```dockerfile
FROM golang:1.23-bookworm AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o server .

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=builder /app/server /server
EXPOSE 8080
ENTRYPOINT ["/server"]
```

```bash
docker build -f golang/Dockerfile.multistage-distroless -t goapp:distroless .
```

| Метрика | Значення |
|---------|----------|
| Розмір образу | **~10 MB** |
| Час збірки | ~17 с |

Distroless-образ — компроміс між scratch і повноцінним debian:

- Містить CA-сертифікати, інформацію про часові зони, `/etc/passwd`.
- Запускається від nonroot-користувача за замовчуванням (краще для безпеки).
- Все ще немає shell та утиліт для дебагу — але існує `debug`-варіант із busybox.

### Порівняльна таблиця (Golang)

| Образ | Розмір | Час збірки | Shell | CA certs | Debug |
|-------|--------|------------|-------|----------|-------|
| Single-stage | ~850 MB | ~15 с | ✅ | ✅ | ✅ |
| Multi-stage scratch | ~8 MB | ~16 с | ❌ | ❌ | ❌ |
| Multi-stage distroless | ~10 MB | ~17 с | ❌ | ✅ | ❌ (є debug-варіант) |

---

## Висновки та рекомендації

1. **Порядок шарів має значення.** Оптимізація порядку `COPY`/`RUN` у Dockerfile
   (спочатку залежності, потім код) радикально зменшує час ребілду — з 15 с до 2 с у нашому
   експерименті. Це найпростіша і найефективніша оптимізація.

2. **Alpine дає значне зменшення розміру** (~82 MB проти ~1.07 GB), але має підводні камені:
   - Бібліотеки з C-розширеннями (numpy, pandas, scipy) потребують компіляції з вихідного
     коду, що збільшує час збірки в рази.
   - musl libc має відмінності у поведінці DNS-резолвера, що може спричинити проблеми
     з service discovery в оркестрованих середовищах.

3. **Для Python-проектів з native-залежностями** (numpy і подібні) debian-based образи
   є кращим вибором: швидша збірка завдяки pre-built wheels, передбачуваніша поведінка
   завдяки glibc.

4. **Для Go-проектів multi-stage build є обов'язковим.** Різниця між single-stage (~850 MB)
   і multi-stage (~8-10 MB) — два порядки. Рекомендується distroless замість scratch для
   production: він додає лише ~2 MB, але містить CA-сертифікати і timezone-дані.

5. **Закріплення версій залежностей** (`pip freeze`, lock-файли) — обов'язкове для
   відтворюваних збірок. Без цього кожна нова збірка може непомітно затягнути нові версії
   бібліотек.
