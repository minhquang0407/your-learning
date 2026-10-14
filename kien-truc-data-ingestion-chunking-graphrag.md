# BÁO CÁO KỸ THUẬT: KIẾN TRÚC DATA INGESTION VÀ CHUNKING BẢO TOÀN NGỮ CẢNH ĐA TẦNG CHO HỆ THỐNG GIA SƯ THÔNG MINH DỰA TRÊN GRAPHRAG

Các Hệ thống Gia sư Thông minh (Intelligent Tutoring Systems - ITS) thế hệ mới đòi hỏi sự kết hợp chặt chẽ giữa hai mô hình tổ chức tri thức: lộ trình học tập phân cấp tuyến tính (Curriculum Hierarchy: Chương -> Mục -> Bài) giúp định hướng người học, và Đồ thị Tri thức (Knowledge Graph - KG) cho phép thực hiện suy luận đa nhảy (multi-hop reasoning) và cá nhân hóa lộ trình [1, 2]. Tuy nhiên, tầng xử lý dữ liệu đầu vào (Data Ingestion & Chunking) thường tạo ra điểm nghẽn kiến trúc nghiêm trọng. Việc cắt nhỏ văn bản theo ranh giới mục lục thuần túy dẫn đến biến động kích thước chunk không kiểm soát, gây ra hiện tượng mất sót thông tin (Lost in the Middle) hoặc đứt gãy ngữ cảnh của khái niệm [3, 4]. Nhu cầu cấp thiết hiện nay là một kiến trúc ingestion đa tầng có khả năng đồng thời bảo toàn khung sư phạm vĩ mô và hỗ trợ bóc tách thực thể vi mô đạt độ sạch tối đa.

---

## 1. SO SÁNH CÁC TRƯỜNG PHÁI CHUNKING TRONG GRAPHRAG

Việc lựa chọn chiến lược chia nhỏ văn bản quyết định trực tiếp đến độ chính xác của quá trình trích xuất đồ thị (Graph Extraction) và hiệu năng tìm kiếm thông tin (Retrieval Performance). Dưới đây là phân tích chuyên sâu các trường phái chunking hàng đầu thế giới hiện nay dưới góc độ kiến trúc GraphRAG.

### 1.1. Phân Tích Chuyên Sâu Các Phương Pháp Chunking

#### Fixed-Size & Overlapping Chunking
Phương pháp cắt văn bản theo cửa sổ token cố định (như 600–1200 tokens với overlap 10–20%) áp dụng thuật toán cửa sổ trượt cơ học. Cách tiếp cận này giúp tối ưu hóa chi phí tính toán ($O(N)$) và đảm bảo kích thước các khối văn bản đồng đều cho các mô hình nhúng (embedding models) [3]. Tuy nhiên, nhược điểm cốt lõi của nó trong các hệ thống sư phạm là phá vỡ hoàn toàn ranh giới ngữ nghĩa và cấu trúc chương mục. Các câu văn định nghĩa khái niệm cốt lõi có thể bị cắt đôi ở ranh giới giữa hai chunk, khiến mô hình ngôn ngữ lớn (LLM) không thể nhận diện được mối quan hệ giữa các thực thể, đồng thời loại bỏ hoàn toàn khả năng định vị vị trí bài học của sinh viên trên cây giáo trình [3, 4].

#### Semantic Chunking
Semantic Chunking đo lường sự biến đổi ngữ nghĩa bằng cách tính toán khoảng cách cosine giữa vector nhúng của các câu liên tiếp, sau đó chia chunk tại các điểm có sự chuyển tiếp chủ đề vượt ngưỡng (threshold) [3]. Phương pháp này tạo ra các khối văn bản có nội dung đồng nhất, giúp LLM trích xuất các bộ ba thực thể - quan hệ (triplets) sạch hơn [3]. Mặc dù vậy, hạn chế của nó nằm ở việc kích thước chunk đầu ra rất thất thường. Đối với các tài liệu kỹ thuật dài, một chủ đề có thể kéo dài qua nhiều trang, dẫn đến chunk vượt quá giới hạn ngữ cảnh hiệu quả của LLM. Chi phí tính toán nhúng ở giai đoạn tiền xử lý cũng tăng lên do phải nhúng từng câu đơn lẻ trước khi gom nhóm [3].

#### Parent-Child / Hierarchical Chunking
Phương pháp phân cấp tạo ra mối liên kết logic giữa các khối văn bản con (Child Chunks, khoảng 200–400 tokens) và khối văn bản cha (Parent Chunks, đại diện cho một Section hoặc Chapter) [5]. Khối con nhỏ gọn được sử dụng để tối ưu hóa điểm số tìm kiếm vector (retrieval precision), trong khi toàn bộ khối cha được trả về cho LLM nhằm cung cấp bối cảnh đầy đủ khi sinh câu trả lời [5]. Điểm yếu của phương pháp này trong bài toán GraphRAG là nếu khối cha quá lớn, LLM vẫn gặp khó khăn khi trích xuất đồ thị tri thức do nhiễu thông tin, đồng thời chi phí lưu trữ chỉ mục gia tăng đáng kể.

#### Contextual Retrieval (Anthropic)
Được giới thiệu bởi Anthropic, chiến lược này giải quyết triệt để tình trạng mất ngữ cảnh bằng cách sử dụng LLM để tạo ra một đoạn tóm tắt bối cảnh ngắn (50–100 tokens) cho từng chunk nhỏ trước khi đưa vào chỉ mục vector và BM25 [6, 7]. Đoạn tóm tắt này giải thích rõ vai trò của chunk trong toàn bộ tài liệu (ví dụ: *"Đoạn này thuộc Chương 3, giải thích thuật toán Gradient Descent trong ngữ cảnh khóa học Machine Learning"*) [6]. Kết hợp với thuật toán Reranking, phương pháp này giúp giảm tới 67% các lỗi truy vấn thất bại [7]. Mặc dù mang lại hiệu năng cao nhất về độ chính xác ngữ cảnh, Contextual Retrieval đòi hỏi chi phí token và độ trễ cực cao trong giai đoạn Ingestion do phải gọi LLM cho hàng nghìn chunk, dù chi phí này có thể được tối ưu một phần nhờ cơ chế Prompt Caching (xuống khoảng 1.02 USD/triệu token tài liệu) [7, 8].

#### Late Chunking (Jina AI)
Do Günther và các cộng sự tại Jina AI phát triển (2024), Late Chunking đảo ngược quy trình truyền thống: thay vì chia nhỏ văn bản rồi mới nhúng, hệ thống đưa toàn bộ văn bản dài (hoặc một macro-chunk lên tới 8192 tokens) qua mô hình Long-Context Embedding (như jina-embeddings-v3) [3, 9, 10]. Chuỗi biểu diễn ẩn (hidden states) của tất cả các token được giữ lại trước tầng gom trung bình (mean pooling) [3, 11]. Sau đó, các ranh giới chunk mới được áp dụng để thực hiện mean pooling trên các đoạn token tương ứng [3, 11]. Do mỗi token vector đã tiếp thu thông tin ngữ cảnh toàn cục hai chiều từ tất cả các token khác trong tài liệu, các chunk thu được mang đầy đủ ngữ cảnh vĩ mô mà không bị đứt gãy liên kết đại từ (anaphora resolution) [4, 10, 12]. Đây là phương pháp tối ưu nhất về chi phí tính toán và bảo toàn ngữ cảnh cho GraphRAG [3, 10].

### 1.2. Bảng So Sánh Tổng Hợp Các Trường Phái Chunking

| Tiêu Chí Đánh Giá | Fixed-Size Window | Semantic Chunking | Parent-Child Chunking | Contextual Retrieval (Anthropic) | Late Chunking (Jina AI) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Độ chính xác Ngữ cảnh Vi mô** | Thấp | Trung bình - Cao | Trung bình | Tối ưu | Tối ưu |
| **Độ chính xác Ngữ cảnh Vĩ mô** | Rất thấp | Thấp | Cao | Tối ưu | Cao |
| **Chi phí Token Ingestion** | Tối thiểu ($O(1)$) | Thấp (chỉ tốn embedding câu) | Trung bình | Rất cao (gọi LLM + Prompt Caching) [7] | Rất thấp (chỉ tốn Long Embedding) [10, 11] |
| **Độ trễ Xử lý (Latency)** | Rất thấp | Trung bình | Trung bình | Rất cao | Thấp |
| **Bảo toàn Cấu trúc Giáo trình** | Không có | Phân mảnh | Tốt | Tối ưu (nhờ Prompting) [6] | Gián tiếp (qua token span) |
| **Chất lượng Trích xuất Entity** | Dễ gãy quan hệ | Tốt ở cấp đoạn | Dễ sót quan hệ xa | Rất cao | Tối ưu |
| **Hiệu năng Truy vấn (nDCG@10)** | Baseline | +5% đến 10% | +10% đến 15% | +20% đến 30% [7] | +15% đến 25% [3, 12] |

---

## 2. KHẢ NĂNG BẢO TOÀN NGỮ CẢNH CỦA ENTITY (ENTITY CONTEXT PRESERVATION)

Trong mô hình sư phạm, một khái niệm tri thức không bao giờ đứng độc lập mà luôn gắn liền với cấp độ bài học và mối quan hệ liên chương. Việc bảo toàn ngữ cảnh thực thể đòi hỏi sự kết hợp giữa ngữ cảnh vi mô trong câu văn và ngữ cảnh vĩ mô trong toàn bộ chương trình học.

### 2.1. Bảo Toàn Ngữ Cảnh Đa Tầng Nhờ Cơ Chế Structural Provenance Injection
Để đảm bảo một thực thể khi được trích xuất không bao giờ bị "mất gốc", hệ thống áp dụng cơ chế tiêm nhãn cấu trúc (Structural Provenance Injection). Khi một khối văn bản được chuẩn bị đưa vào mô hình ngôn ngữ để trích xuất thực thể, hệ thống sẽ gộp một tiền tố ngữ cảnh định dạng (Contextual Header Prefix) trực tiếp vào đầu đoạn văn. Tiền tố này được tổng hợp tự động từ Cây Phân cấp Mục lục, tạo thành chuỗi định danh định hướng cho LLM.

Thông qua tiền tố ngữ cảnh này, LLM khi thực hiện nhiệm vụ Rút trích Thực thể và Quan hệ (NER & RE) sẽ không chỉ đọc nội dung thuần túy của chunk mà còn nhận biết được vị trí chính xác của chunk đó trong không gian sư phạm. Mọi thực thể và quan hệ được trích xuất ra sẽ được tự động gắn kèm các tập thuộc tính định danh kép (Dual-Key Metadata), bao gồm mã định danh tài liệu, mã định danh chương, mã định danh mục, cùng với mã băm MD5 duy nhất của chunk chứa nó [13]. Định danh này tạo ra khả năng truy xuất nguồn gốc chính xác (provenance tracing) từ một nút trên Đồ thị Tri thức ngược về đúng vị trí dòng văn bản trong tài liệu gốc [13, 14].

Đồng thời, quá trình mã hóa vector cho chunk này sử dụng kỹ thuật Late Chunking [3]. Mô hình nhúng long-context xử lý toàn bộ đoạn văn bản lớn chứa section, giúp cho vector đại diện của chunk vi mô mang theo thông tin toàn cục của toàn bộ section đó [3, 10]. Điều này giúp câu lệnh tìm kiếm ngữ nghĩa ở tầng vi mô vẫn kích hoạt chính xác các khối kiến thức nằm trong bối cảnh vĩ mô phù hợp [12].

### 2.2. Xử Lý Thực Thể Xuất Hiện Xuyên Suốt Nhiều Chương (Cross-Chapter Entity Resolution)
Hiện tượng phân tán thực thể (Entity Fragmentation) là một thách thức lớn trong xây dựng Đồ thị Tri thức Giáo trình: một khái niệm được giới thiệu ở Chương 1 dưới dạng lý thuyết cơ bản có thể xuất hiện lại ở Chương 5 dưới dạng thuật toán và Chương 10 dưới dạng bài tập ứng dụng. Nếu không có cơ chế hợp nhất, đồ thị sẽ bị cô lập thành các đảo tri thức rời rạc.

Hệ thống giải quyết bài toán này thông qua Quy trình Hợp nhất Đồ thị Đa giai đoạn (Graph Consolidation Pipeline) [13]:

1. **Trích xuất Chuẩn hóa (Canonical Extraction):** Hệ thống thực hiện trích xuất thực thể theo định dạng chuẩn hóa được kiểm soát bởi Pydantic Schema [13, 15]. Mô hình LLM được yêu cầu trích xuất tên chuẩn (canonical name), loại thực thể (type), và các từ đồng nghĩa/biến thể tên gọi (aliases) [16].

2. **Phân nhóm Thực thể (Entity Resolution):** Hệ thống khởi chạy thuật toán phân nhóm thực thể [13]. Bằng cách tính toán độ tương đồng vector giữa mô tả các thực thể cùng loại kết hợp với so khớp chuỗi ký tự Levenshtein trên tên gọi và biến thể, các thực thể trùng lặp xuất hiện ở các chương khác nhau sẽ được gom về một Canonical Entity Node duy nhất [13]. Kỹ thuật phân nhóm mật độ DBSCAN được áp dụng trên không gian embedding của thực thể để tự động phát hiện các cụm thực thể đồng nhất mà không cần cố định số lượng cụm [13].

3. **Hợp nhất và Thiết lập Quan hệ Sư phạm (Pedagogical Edges):** Sau khi hợp nhất các nút thực thể trùng lặp, một bước tổng hợp bằng LLM (LLM Summarization) sẽ hòa trộn các đoạn mô tả phân tán ở từng chương thành một văn bản định nghĩa toàn diện [13]. Đồng thời, các cạnh quan hệ sư phạm (Pedagogical Edges) được thiết lập giữa Canonical Entity Node với các mục trong cây phân cấp bài học, ví dụ:
   - `(Entity) -[:INTRODUCED_IN]-> (Section_Ch1)`
   - `(Entity) -[:EXEMPLIFIED_IN]-> (Section_Ch5)`
   - `(Entity) -[:ASSESSED_IN]-> (Section_Ch10)`

Hệ thống cũng tự động xây dựng các quan hệ phụ thuộc sư phạm giữa các thực thể dựa trên thứ tự xuất hiện trên cây mục lục, chẳng hạn như `(Concept_A) -[:PREREQUISITE_OF]-> (Concept_B)`, tạo nền tảng cho AI Tutor đề xuất lộ trình học bù kiến thức khi sinh viên gặp hổng kiến thức [2].

---

## 3. XỬ LÝ TÀI LIỆU ĐA PHƯƠNG THỨC VÀ MẤT CẤU TRÚC (DEGRADED INPUTS)

Dữ liệu đầu vào trong các hệ thống giáo dục thực tế rất đa dạng và thường xuyên thiếu chuẩn hóa, từ các tệp trình chiếu Slide (.pptx) chứa ít văn bản đến các tệp PDF phẳng đã bị loại bỏ hoàn toàn các thẻ định dạng phân cấp.

### 3.1. Đơn Vị Chunking Tự Nhiên Cho Dạng Tài Liệu Slide (.pptx, PDF Slides)
Tài liệu Slide bài giảng có đặc thù cấu trúc khác biệt so với giáo trình dạng văn bản liền mạch. Mật độ chữ trên mỗi trang slide rất thấp, nhưng tính đóng gói ý tưởng lại rất cao. Do đó, việc áp dụng các bộ chia văn bản theo số lượng token hay câu trên slide là không phù hợp.

Đơn vị Chunking tự nhiên cho Slide được xác định là **Một Trang Slide Đơn Lẻ (Single Slide Unit)**. Một Chunk Slide hoàn chỉnh được cấu thành bởi sự hợp nhất dữ liệu đa phương thức bao gồm:
- Tiêu đề slide (Slide Title - đóng vai trò là nhãn mục lục cấp nhỏ nhất)
- Nội dung các điểm gạch đầu dòng (Bullet Points - đóng vai trò là các khẳng định tri thức nguyên tử)
- Phần ghi chú của giảng viên (Speaker Notes - cung cấp văn bản diễn giải ngữ cảnh chi tiết)
- Các thông tin cấu trúc chuyển đổi từ hình ảnh/bảng biểu.

Trong quá trình xử lý, hệ thống triển khai kỹ thuật gom nhóm slide thông minh: nếu hai hoặc nhiều slide liên tiếp có chung tiêu đề chính và chứa các từ khóa nối (như *"tiếp theo"*, *"phần 2"*), chúng sẽ được hợp nhất thành một Macro-Slide Chunk để giữ trọn bối cảnh giảng dạy trước khi đưa vào mô hình Late Chunking [3].

### 3.2. Khôi Phục Cấu Trúc Phân Cấp Cho PDF Mất Định Dạng (Degraded Flat PDFs)
Các tệp PDF "phẳng" (không có thẻ đánh dấu Header #, ## hoặc Outline Tree) gây tê liệt cho các bộ chia văn bản dựa trên quy tắc chuỗi. Việc chuyển toàn bộ PDF cho LLM để đọc và khôi phục cấu trúc phân cấp là giải pháp tiêu tốn chi phí token rất lớn và có độ trễ không thể chấp nhận được trong môi trường vận hành thực tế.

Giải pháp tối ưu là triển khai luồng xử lý 3 tầng kết hợp giữa Thị giác Máy tính (Computer Vision) nhẹ và các thuật toán quy tắc cấu trúc:

- **Tầng 1 (Visual Document Layout Analysis - DLA):** Áp dụng các mô hình Nhận diện Bố cục Tài liệu dựa trên Thị giác chạy hoàn toàn cục bộ trên hạ tầng nội bộ, điển hình như engine **Docling** với mô hình heron-101 [17, 18], hoặc **Marker** và **MinerU** [17, 19]. Các mô hình này không dùng LLM mà sử dụng các mạng Vision Transformer nhỏ để phân tích hình ảnh trang PDF, tự động xác định tọa độ không gian (bounding boxes) và phân loại từng khối nội dung thành các nhãn: Title, Section-Header, Text, Table, Picture [17]. Quá trình này diễn ra với tốc độ rất nhanh, chỉ từ 1.27 đến 3.1 giây mỗi trang trên phần cứng tiêu chuẩn [17].
- **Tầng 2 (Font-Attribute Hierarchy Reconstruction):** Triển khai Thuật toán Phân cấp dựa trên Thuộc tính Phông chữ. Hệ thống thực hiện trích xuất thuộc tính phông chữ (font size, font weight, font family) của các khối được gắn nhãn Section-Header. Bằng thuật toán phân nhóm dữ liệu k-means đơn giản trên kích thước phông chữ, hệ thống xác định được quy luật phân cấp:
  - Kích thước phông chữ lớn nhất có tần suất xuất hiện thấp ($S_{max}$) được gắn nhãn Chapter / H1.
  - Kích thước phông chữ trung bình ($S_{med}$) được gắn nhãn Section / H2.
  - Các khối văn bản in đậm có tiền tố đánh số (như 1.1, 1.2.1) được gắn nhãn Lesson / H3.
- **Tầng 3 (Lightweight LLM Validation):** Bước Kiểm tra Hiệu chỉnh nhẹ. Hệ thống chỉ trích xuất danh sách các câu tiêu đề đã được khôi phục kèm theo cấp độ dự đoán (không gửi toàn bộ nội dung văn bản) và gửi một câu lệnh đến mô hình LLM nhỏ (như Qwen2.5-7B) để xác nhận tính logic của Cây Mục lục. Phương pháp này giảm hơn 95% chi phí token so với việc xử lý toàn bộ văn bản bằng LLM, trong khi vẫn đảm bảo độ chính xác khôi phục cấu trúc đạt trên 90% [17].

---

## 4. ĐỀ XUẤT KIẾN TRÚC TỐI ƯU CHO HỆ THỐNG AI TUTOR (PRODUCTION-READY ARCHITECTURE)

Nhằm giải quyết triệt để bài toán được đặt ra, kiến trúc được đề xuất dưới đây kết hợp hài hòa giữa việc duy trì Cây Mục lục Giáo trình cho sinh viên và việc trích xuất Đồ thị Tri thức sạch phục vụ tính năng GraphRAG.

### 4.1. Luồng Chuyển Đổi Dữ Liệu Tổng Thể (Data Pipeline Flow)

Luồng xử lý dữ liệu được thiết kế gồm 5 giai đoạn nối tiếp nhau, đảm bảo dữ liệu được làm sạch và làm phong phú ngữ cảnh trước khi lưu trữ vào các cơ sở dữ liệu chuyên dụng:

1. **Giai đoạn 1 (Structural Ingestion & Layout Parsing):** Tài liệu đầu vào (PDF, PPTX, DOCX) được đưa qua engine Docling [17, 20]. Mô hình thị giác cục bộ phân tích bố cục, trích xuất hình ảnh, bảng biểu và thứ tự đọc chính xác, tạo ra đối tượng dữ liệu cấu trúc chuẩn hóa `DoclingDocument` [17, 19, 20].
2. **Giai đoạn 2 (Pedagogical Hierarchy Mapping):** Hệ thống quét qua `DoclingDocument` để xây dựng Cây Phân cấp Mục lục (Curriculum Hierarchy Tree) bao gồm các nút phân cấp từ Document đến Chapter, Section và Lesson. Mỗi nút được cấp một mã định danh UUID cố định và chuỗi đường dẫn phân cấp (Breadcrumb Path).
3. **Giai đoạn 3 (Parent-Child Late Chunking & Embedding):** Hệ thống tạo các khối văn bản theo mô hình cha-con [5]. Khối cha đại diện cho trọn vẹn một Section. Khối con được chia ở kích thước 256–512 tokens. Chuỗi token của khối cha được đưa qua mô hình `jina-embeddings-v3` để tính toán các vector Late Chunking cho từng khối con, đảm bảo mỗi khối con mang đầy đủ ngữ cảnh vĩ mô của phần bài học [3, 9, 10].
4. **Giai đoạn 4 (Two-Stage Schema-Guided Graph Extraction):** Các khối văn bản kèm theo tiền tố bối cảnh cấu trúc được chuyển đến mô hình ngôn ngữ để trích xuất tri thức theo quy trình 2 bước [13]:
   - *Bước 1:* LLM trích xuất các Thực thể và đối soát với Từ điển Từ vựng Khái niệm (Ontology) [13, 14].
   - *Bước 2:* LLM trích xuất các Mối quan hệ giữa các thực thể đã được xác nhận ở Bước 1 [13].
   - Định dạng đầu ra được ép buộc nghiêm ngặt bằng Pydantic Schema để đảm bảo tính type-safe [1, 15].
5. **Giai đoạn 5 (Consolidation & Dual-Storage Sync):** Hệ thống chạy thuật toán DBSCAN để hợp nhất các thực thể trùng lặp xuyên suốt các chương [13]. Sau đó, dữ liệu được đồng bộ đồng thời vào hai cơ sở dữ liệu:
   - Các vector Late Chunking và metadata cấu trúc được đẩy vào Vector Database (như Qdrant hoặc Milvus) [21].
   - Cấu trúc Cây Mục lục và Đồ thị Tri thức Thực thể - Quan hệ được đẩy vào Graph Database (như Neo4j hoặc HydraDB) [1, 15].

### 4.2. Cấu Trúc Schema Dữ Liệu Mẫu (Pydantic / Python)

Dưới đây là mô hình dữ liệu Pydantic hoàn chỉnh thể hiện chính xác mối liên kết phân cấp từ Document -> Chapter -> Section -> Chunk -> Entity, sẵn sàng triển khai trong môi trường Production [1, 15]:

```python
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

# --- 1. TẦNG CẤU TRÚC GIÁO TRÌNH (CURRICULUM HIERARCHY) ---

class HierarchyLevel(str, Enum):
    DOCUMENT = "DOCUMENT"
    CHAPTER = "CHAPTER"
    SECTION = "SECTION"
    LESSON = "LESSON"

class CurriculumNode(BaseModel):
    node_id: str = Field(..., description="UUID định danh duy nhất của nút mục lục")
    title: str = Field(..., description="Tiêu đề chương, mục hoặc bài học")
    level: HierarchyLevel = Field(..., description="Cấp độ phân cấp sư phạm")
    parent_id: Optional[str] = Field(None, description="ID của nút cha trên cây mục lục")
    breadcrumb_path: str = Field(..., description="Đường dẫn đầy đủ, ví dụ: 'Toán Cao Cấp > Chương 2 > Mục 2.1'")
    order_index: int = Field(..., description="Thứ tự xuất hiện tuyến tính trong giáo trình")

# --- 2. TẦNG CHUNK VĂN BẢN VÀ EMBEDDING (TEXT CHUNK LEVEL) ---

class TextChunk(BaseModel):
    chunk_id: str = Field(..., description="Mã băm MD5 dựa trên nội dung và vị trí")
    parent_section_id: str = Field(..., description="Mã ID của Section chứa chunk này")
    text_content: str = Field(..., description="Nội dung văn bản thô của chunk")
    context_prefix: str = Field(..., description="Tiền tố bối cảnh cấu trúc được tiêm vào từ CurriculumNode")
    start_char_offset: int = Field(..., description="Vị trí ký tự bắt đầu trong tài liệu gốc")
    end_char_offset: int = Field(..., description="Vị trí ký tự kết thúc trong tài liệu gốc")
    embedding_vector: Optional[List[float]] = Field(None, description="Vector nhúng Late Chunking")

# --- 3. TẦNG ĐỒ THỊ TRI THỨC SƯ PHẠM (PEDAGOGICAL KNOWLEDGE GRAPH) ---

class EntityType(str, Enum):
    CONCEPT = "CONCEPT"              # Khái niệm lý thuyết
    FORMULA = "FORMULA"              # Công thức toán/khoa học
    ALGORITHM = "ALGORITHM"          # Thuật toán/Quy trình
    EXAMPLE = "EXAMPLE"              # Ví dụ minh họa
    MISCONCEPTION = "MISCONCEPTION"  # Hiểu lầm phổ biến của sinh viên

class PedagogicalRelationType(str, Enum):
    PREREQUISITE_OF = "PREREQUISITE_OF"  # Khái niệm A là kiến thức tiên quyết của B
    CORE_CONCEPT_OF = "CORE_CONCEPT_OF"  # A là khái niệm cốt lõi của Bài học X
    APPLIED_IN = "APPLIED_IN"            # Khái niệm A được ứng dụng trong B
    EXEMPLIFIES = "EXEMPLIFIES"          # B là ví dụ minh họa cho A
    DEPENDS_ON = "DEPENDS_ON"            # Quan hệ phụ thuộc tổng quát

class EntityNode(BaseModel):
    entity_id: str = Field(..., description="Canonical ID chuẩn hóa của thực thể")
    canonical_name: str = Field(..., description="Tên chuẩn hóa của thực thể")
    aliases: List[str] = Field(default_factory=list, description="Các từ đồng nghĩa hoặc tên gọi khác")
    entity_type: EntityType = Field(..., description="Phân loại thực thể sư phạm")
    description: str = Field(..., description="Mô tả tóm tắt được tổng hợp xuyên suốt các chương")
    source_chunk_ids: List[str] = Field(..., description="Danh sách các Chunk ID chứa thực thể này (Provenance)")

class KnowledgeEdge(BaseModel):
    edge_id: str = Field(..., description="UUID định danh duy nhất của quan hệ")
    source_entity_id: str = Field(..., description="ID của thực thể nguồn")
    target_entity_id: str = Field(..., description="ID của thực thể đích")
    relation_type: PedagogicalRelationType = Field(..., description="Loại quan hệ sư phạm")
    description: str = Field(..., description="Giải thích chi tiết ngữ cảnh của mối quan hệ")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Độ tin cậy của trích xuất")
    origin_section_id: str = Field(..., description="Section phát hiện ra mối quan hệ này")

# --- 4. TRỌNG TẢI DỮ LIỆU TỔNG HỢP (INVOICE / PAYLOAD CONTAINER) ---

class DocumentIngestionPayload(BaseModel):
    document_id: str = Field(..., description="ID duy nhất của tài liệu đầu vào")
    title: str = Field(..., description="Tên tài liệu/môn học")
    curriculum_hierarchy: List[CurriculumNode] = Field(..., description="Danh sách các nút trên cây mục lục")
    chunks: List[TextChunk] = Field(..., description="Danh sách các chunk văn bản đã được tạo embedding")
    extracted_entities: List[EntityNode] = Field(..., description="Danh sách các thực thể đã được hợp nhất")
    extracted_edges: List[KnowledgeEdge] = Field(..., description="Danh sách các quan hệ tri thức")
```

### 4.3. Phân Tích Chi Phí Và Đánh Đổi Kiến Trúc (Trade-Offs Analysis)

Mọi kiến trúc hệ thống chuyên sâu đều đòi hỏi sự cân bằng giữa chi phí vận hành, độ trễ xử lý và độ phức tạp triển khai.

#### Bảng So Sánh Các Yếu Tố Kỹ Thuật Khi Triển Khai

| Công Đoạn System | Giải Pháp Lựa Chọn | Chi Phí Token API | Độ Trễ Xử Lý (Latency) | Độ Phức Tạp Triển Khai |
| :--- | :--- | :--- | :--- | :--- |
| **Document Parsing** | **Docling** (Visual DLA Local) [17, 19] | 0 USD (Chạy hoàn toàn trên hạ tầng CPU/GPU nội bộ) [17] | ~1.2 – 3.1 giây / trang [17] | Trung bình (Cần quản lý Container và thư viện PyTorch/ONNX) [22]. |
| **Chunking & Vectoring** | **Parent-Child Late Chunking** (`jina-embeddings-v3`) [9, 10] | Thấp (Chỉ tốn phí nhúng cho chuỗi token, không gọi LLM) [10] | < 100ms cho mỗi Macro Chunk 8k tokens | Trung bình (Cần triển khai mô hình Long-Context Embedding tương thích) [3, 9]. |
| **Graph Extraction** | **Two-Stage Schema-Guided Extraction** (Qwen2.5-72B / GPT-4o) [13] | Cao (Tốn 2 lượt gọi LLM kèm theo Pydantic Schema cho mỗi chunk) [13, 15] | 2.0 – 4.5 giây / chunk | Cao (Cần xử lý lỗi JSON Schema Validation và Retry Mechanism) [15]. |
| **Entity Resolution** | **DBSCAN + Structural LLM Merge** [13] | Trung bình (Chỉ gọi LLM xử lý các cụm thực thể trùng lặp) | Chạy bất đồng bộ (Batch Job) | Rất cao (Cần duy trì trạng thái đồ thị và quản lý phiên bản dữ liệu) [1]. |

#### Đánh Giá Tổng Thể Tính Tối Ưu
- **Về mặt Chi phí Vận hành (Operational Cost):** Việc sử dụng Docling cho giai đoạn phân tích bố cục thị giác giúp loại bỏ hoàn toàn chi phí đắt đỏ của các dịch vụ SaaS OCR thương mại [17]. Đồng thời, việc ứng dụng Late Chunking thay thế cho chiến lược Contextual Retrieval giúp tiết kiệm tới 70% chi phí token API ở khâu tạo chỉ mục vector, do không phải sử dụng LLM để sinh văn bản tóm tắt bối cảnh cho từng chunk nhỏ [6, 7, 10]. Chi phí API chủ yếu tập trung vào giai đoạn trích xuất đồ thị tri thức (Graph Extraction), nơi chất lượng của mô hình ngôn ngữ quyết định độ sạch của dữ liệu [13].
- **Về mặt Giá trị Sư phạm (Pedagogical Value):** Kiến trúc này giải quyết trọn vẹn hai nhu cầu khắt khe của một AI Tutor chuyên nghiệp. Cây Phân cấp Mục lục được bảo toàn giúp giao diện người dùng luôn hiển thị chính xác tiến trình học tập tuyến tính (Chương -> Mục -> Bài). Cùng lúc đó, Đồ thị Tri thức Đa tầng được trích xuất sạch sẽ cung cấp cho công cụ GraphRAG khả năng trả lời các câu hỏi tổng hợp, phân tích mối liên hệ tiên quyết giữa các khái niệm phân tán ở các chương khác nhau, và tự động đề xuất bài học bù khi phát hiện sinh viên bị hổng kiến thức [1, 2].

---

## 5. KẾT LUẬN

Bài toán kiến trúc tầng Data Ingestion & Chunking cho Hệ thống Gia sư Thông minh dựa trên GraphRAG đòi hỏi sự kết hợp đồng bộ giữa các kỹ thuật tiên tiến nhất giai đoạn 2024–2025:

1. **Loại bỏ cách cắt văn bản cơ học** để chuyển sang mô hình Ingestion cấu trúc thị giác bằng các công cụ như Docling, giúp khôi phục chính xác Cây Mục lục Giáo trình từ cả các tệp PDF bị mất định dạng mà không tốn chi phí LLM [17, 19].
2. **Áp dụng Late Chunking** để nhúng các khối văn bản, đảm bảo tính toàn vẹn của ngữ cảnh vi mô và vĩ mô mà không làm đứt gãy liên kết đại từ của thực thể [3, 4, 10].
3. **Triển khai quy trình trích xuất đồ thị hai bước** được kiểm soát chặt chẽ bằng Pydantic Schema, kết hợp với thuật toán Phân nhóm DBSCAN để hợp nhất thực thể xuyên suốt các chương, tạo ra một Đồ thị Tri thức Sư phạm có khả năng truy xuất nguồn gốc chính xác [13, 14, 15].

Việc áp dụng toàn bộ thiết kế kiến trúc này đảm bảo cho hệ thống AI Tutor vận hành hiệu quả ở quy mô lớn, vừa giữ vững lộ trình học tập trực quan cho sinh viên, vừa mang lại khả năng suy luận tri thức sâu sắc cho mô hình trí tuệ nhân tạo [1, 2].

---

## TÀI LIỆU THAM KHẢO

1. Best GraphRAG Platforms for Pydantic AI in 2026 - HydraDB, https://hydradb.com/blog/graphrag-platforms-pydantic-ai
2. K12-KGraph: A Curriculum-Aligned Knowledge Graph for ... - HyperAI, https://hyper.ai/en/papers/2605.09635
3. Late Chunking: Contextual Chunk Embeddings Using Long-Context Embedding Models - arXiv, https://arxiv.org/pdf/2409.04701
4. Late Chunking: Contextual Chunk Embeddings Using Long-Context Embedding Models - arXiv, https://arxiv.org/html/2409.04701v1
5. Advanced RAG Chunking 2026: Late, Semantic, Parent-Child - Future AGI, https://futureagi.com/blog/advanced-chunking-techniques-for-rag/
6. Cross-Document Topic-Aligned Chunking for Retrieval-Augmented Generation - arXiv, https://arxiv.org/html/2601.05265v1
7. Anthropic Contextual Retrieval (2024) Explained, With Code - CallSphere, https://callsphere.ai/blog/vw6g-anthropic-contextual-retrieval-2026-revisit
8. Contextual Retrieval: Anthropic's RAG Fix Explained | MemX, https://memx.app/glossary/contextual-retrieval/
9. Late Chunking: Contextual Chunk Embeddings Using Long-Context Embedding Models | OpenReview, https://openreview.net/forum?id=74QmBTV0Zf
10. What Late Chunking Really Is & What It's Not: Part II, https://jina.ai/news/what-late-chunking-really-is-and-what-its-not-part-ii/
11. Paper page - Late Chunking: Contextual Chunk Embeddings Using Long-Context Embedding Models - Hugging Face, https://huggingface.co/papers/2409.04701
12. GitHub - jina-ai/late-chunking: Code for explaining and evaluating late chunking (chunked pooling), https://github.com/jina-ai/late-chunking
13. RAGU: A Multi-Step GraphRAG Engine with a Compact Domain-Adapted LLM - arXiv, https://arxiv.org/html/2607.11683v1
14. Ontology Generation & Entity Extraction Tools 2026 - Cognee, https://www.cognee.ai/automatic-ontology-generation-tools
15. Entity extraction with LLMs – from document to knowledge graph - Till Freitag, https://till-freitag.com/en/blog/entity-extraction-llm-knowledge-graph-en
16. GraphRAG Implementation with LlamaIndex | Developer Documentation, https://developers.llamaindex.ai/python/examples/cookbooks/graphrag_v1/
17. arXiv:2501.17887v1 [cs.CL] 27 Jan 2025, https://arxiv.org/pdf/2501.17887
18. Advanced Layout Analysis Models for Docling - arXiv, https://arxiv.org/html/2509.11720v1
19. Parsing PDFs for LLM input – Nicolas Brosse, https://nbrosse.github.io/posts/pdf-parsing/pdf-parsing.html
20. docling-workshops/workshops/2025_09_24/docling_lab_1.ipynb at main - GitHub, https://github.com/docling-project/docling-workshops/blob/main/workshops/2025_09_24/docling_lab_1.ipynb
21. API Documentation — neo4j-graphrag-python documentation, https://neo4j.com/docs/neo4j-graphrag-python/current/api.html
22. Docling vs MinerU vs Marker (2026): Code and Model Licenses - Particula Tech, https://particula.tech/blog/docling-vs-mineru-vs-marker-pdf-parser
