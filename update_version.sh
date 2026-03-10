#!/bin/bash
# Script para atualizar VERSION.txt quando cria tag

VERSION=$(git describe --tags --abbrev=0 | sed 's/v//')
echo "$VERSION" > VERSION.txt
git add VERSION.txt
git commit -m "chore: atualizar versão para $VERSION"
git push origin main

echo "✅ VERSION.txt atualizado para $VERSION"
