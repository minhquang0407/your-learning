# Universal LCOV & Test Runner Guide

Proven's **Universal Engine (Track 2)** uses standard **LCOV (`lcov.info`)** or Go **coverprofile (`coverage.out`)** reports to verify Runtime Proof Gates across any programming language.

---

## Cheat Sheet: Generating Coverage Reports by Language

### 1. TypeScript & JavaScript

#### Jest
```bash
# Run specific test file with LCOV report
npx jest tests/my_feature.test.ts --coverage --coverageReporters="lcov"
# Outputs: coverage/lcov.info
```

#### Vitest
```bash
# Run specific test file with LCOV report
npx vitest run tests/my_feature.test.ts --coverage --coverage.reporter="lcov"
# Outputs: coverage/lcov.info
```

---

### 2. Go

```bash
# Run tests with native coverprofile
go test -coverprofile=coverage.out ./...
# Outputs: coverage.out
```

---

### 3. Rust

```bash
# Using cargo-llvm-cov
cargo llvm-cov --lcov --output-path coverage/lcov.info
# Outputs: coverage/lcov.info
```

---

### 4. Python (Universal mode / Pytest)

```bash
pytest --cov --cov-report=lcov:coverage/lcov.info
# Outputs: coverage/lcov.info
```

---

### 5. Java (Maven / Gradle)

- **Maven**: `mvn test` with JaCoCo plugin configured -> `target/site/jacoco/jacoco.xml` or lcov.
- **Gradle**: `gradle test jacocoTestReport`

---

## Verifying Proof with Proven

Once the coverage file is generated, the Coding Agent can verify runtime proof immediately:

```bash
python skills/proven/scripts/verify_runtime_proof.py \
  --target "FUNC:calculateTotal" \
  --lcov "coverage/lcov.info"
```

Or let Proven execute the command and verify in one step:

```bash
python skills/proven/scripts/verify_runtime_proof.py \
  --target "FUNC:calculateTotal" \
  --test-cmd "npx vitest run tests/order.test.ts --coverage --coverage.reporter=lcov"
```
