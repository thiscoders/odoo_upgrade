# 自动升级工具
*基于docker-compose的应用自动升级服务*

### 2019-03-28

## 报文可选参数
```json
{"device": ["curl","siri","wget"],"operate": ["pull","restart","smart"]}
```

## 请求实例1
```shell
curl --request POST --url http://127.0.0.1:8070 \
    --header 'Content-Type: application/json'  \
    --header 'cache-control: no-cache' \
    --data '{"device": "curl","operate": "smart"}'
```

## 请求实例2
```shell
curl -X POST http://127.0.0.1:8070 \
    -H 'Content-Type: application/json' \
    -H 'cache-control: no-cache' \
    -d '{"device": "curl","operate": "smart"}'
```

## 请求实例3
```shell
wget --quiet \
  --method POST \
  --header 'Content-Type: application/json' \
  --header 'cache-control: no-cache' \
  --body-data '{"device": "curl","operate": "smart"}' \
  --output-document \
  - http://127.0.0.1:8070
```