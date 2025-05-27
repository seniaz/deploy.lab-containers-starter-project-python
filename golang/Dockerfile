FROM golang:1.23-bookworm

WORKDIR /app

COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN go build -o server .

EXPOSE 8080

CMD ["./server"]
