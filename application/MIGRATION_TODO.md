# Application-Layer Migration TODO

Mục tiêu: tách business logic khỏi Streamlit mà chưa cần Backend API và chưa rewrite toàn bộ hệ thống.

## Nguyên tắc biên

- `application/` không được import `streamlit`, FastAPI hoặc SDK frontend.
- Frontend chỉ gọi `LearningApplication`; không gọi trực tiếp Qdrant, Neo4j, LLM hoặc `RuntimeEngine`.
- `database/`, `runtime/`, `agents/` không biết frontend đang dùng công nghệ gì.
- Long-running operations phát `ApplicationEvent`; frontend tự quyết định cách render.

## Thứ tự tự triển khai đề xuất

### 1. Library read models

- [ ] Implement `LibraryService.list_documents()`.
- [ ] Implement `LibraryService.get_curriculum()`.
- [ ] Implement `LibraryService.get_progress()`.
- [ ] Implement `LibraryService.get_graph()`.
- [ ] Thay sidebar queries trực tiếp trong `main.py` bằng các method trên.

### 2. QA boundary

- [ ] Implement `QAService.ask()` bằng cách wrap `RuntimeEngine.process_action()`.
- [ ] Validate `LOCAL_QA` và `GLOBAL_QA` tại boundary.
- [ ] Bổ sung citations/retrieved contexts vào `AnswerResult.metadata`.
- [ ] Thay QA block trong `main.py` bằng facade call.

### 3. Lesson event stream

- [ ] Implement `LearningService.stream_lesson()`.
- [ ] Viết mapper từ event dictionary cũ sang `ApplicationEvent`.
- [ ] Chỉ update UI state sau `FINAL`; xử lý `ERROR` mà không tăng `seq_idx`.
- [ ] Thay flow LEARNING trong `main.py`.

### 4. Assessment

- [ ] Implement generate/grade methods.
- [ ] Tạo typed DTO cho quiz và grading thay vì trả dictionary.
- [ ] Di chuyển session-state cache policy sang presentation layer, không đặt trong service.

### 5. Ingestion cuối cùng

- [ ] Port pipeline từ `core/data_ingestion.py` sang `IngestionService`.
- [ ] Thay toàn bộ `st.*` bằng event yield.
- [ ] Thêm retry từng section, cancellation và resumability.
- [ ] Khi chuyển xong, biến file cũ thành adapter tạm hoặc xóa nó.

### 6. Container wiring

- [ ] Thêm providers cho 5 services và `LearningApplication` vào `core/container.py`.
- [ ] Không thay singleton lifetime cho runtime/database trước khi có concurrency tests.
- [ ] Inject facade vào frontend entry point.

### 7. Xóa coupling còn lại

- [ ] `grep -R "streamlit" core application agents runtime database orchestrator` phải không còn kết quả ngoài adapter/UI.
- [ ] `main.py` không còn `.vector_db`, `.graph_db`, `.orchestrator`, `.support_agent`.
- [ ] Tách UI components sau khi application boundary hoạt động ổn định.

## Definition of Done

- [ ] Có thể gọi tất cả use case từ một script Python mà không import Streamlit.
- [ ] Unit tests dùng fake stores/fake LLM, không cần Docker.
- [ ] Streamlit hiện tại vẫn chạy trong suốt quá trình migration.
- [ ] Việc thay Streamlit bằng UI khác không yêu cầu sửa `agents/`, `runtime/`, hoặc `database/`.
