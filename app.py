import streamlit as st
import pandas as pd
from google import genai
from apify_client import ApifyClient

# 1. 페이지 기본 설정
st.set_page_config(page_title="AI 마케팅 올인원 툴", layout="wide")
st.title("✨ AI 마케팅 올인원 툴")
st.markdown("인플루언서 발굴부터 맞춤형 섭외 메시지 작성까지 한 번에 끝내세요.")

# 고정 API 키 설정
GEMINI_KEY = "AQ.Ab8RN6LCth3UNX4taroMZ1hqh57YFmYwWfkfw2Yi-R93FVgwbg"
APIFY_TOKEN = "apify_api_bjEdwAY1D8iyURBVYsSxAqaCBBxfsL0X9CQ4"

# 2. 기능별 탭(Tab) 분리
tab1, tab2 = st.tabs(["🚀 1단계: 인플루언서 발굴 및 분석", "✉️ 2단계: 섭외 메시지 자동 생성"])

# ==========================================
# [탭 1] 기존 인플루언서 자동 추출기 로직
# ==========================================
with tab1:
    with st.sidebar:
        st.header("🔍 발굴 조건 세팅 (1단계용)")
        search_hashtag = st.text_input("해시태그 (# 제외)", value="야구직관")
        max_posts = st.slider("추출할 계정 수", min_value=5, max_value=100, value=10, step=5)
        brand_target = st.text_area("AI 판별 기준", value="야구(KBO)를 진심으로 좋아하고, 경기장 직관 콘텐츠를 올리며 팬들과 소통하는 인플루언서")
        run_btn = st.button("🚀 데이터 추출 및 분석 시작", use_container_width=True)

    if run_btn:
        if not search_hashtag:
            st.error("해시태그를 입력해 주세요.")
        else:
            with st.spinner(f"#{search_hashtag} 관련 계정을 추출하고 AI로 분석 중입니다..."):
                try:
                    client = genai.Client(api_key=GEMINI_KEY)
                    apify_client = ApifyClient(APIFY_TOKEN)

                    run = apify_client.actor("apify/instagram-hashtag-scraper").call(
                        run_input={"hashtags": [search_hashtag], "resultsLimit": max_posts}
                    )
                    
                    dataset_id = run.get("defaultDatasetId") if isinstance(run, dict) else getattr(run, "default_dataset_id", None)
                    if not dataset_id:
                        dataset_id = run.get("default_dataset_id") if isinstance(run, dict) else run.default_dataset_id

                    user_data_map = {}
                    for item in apify_client.dataset(dataset_id).iterate_items():
                        username = item.get("ownerUsername", "알 수 없음")
                        if username not in user_data_map:
                            user_data_map[username] = {
                                "fullName": item.get("ownerFullName", "이름 없음"),
                                "likes": [], 
                                "captions": []
                            }
                        user_data_map[username]["likes"].append(item.get("likesCount", -1))
                        caption = item.get("caption", "")
                        if caption:
                            user_data_map[username]["captions"].append(caption)

                    final_list = []
                    progress_bar = st.progress(0)
                    total_users = len(user_data_map)
                    
                    for idx, (username, info) in enumerate(user_data_map.items()):
                        valid_likes = [l for l in info["likes"] if l != -1 and l is not None]
                        if valid_likes:
                            recent_likes = valid_likes[:9]
                            avg_likes = sum(recent_likes) / len(recent_likes)
                            avg_likes_str = f"{round(avg_likes, 1):,}개"
                        else:
                            avg_likes_str = "비공개 (숨김)"
                        
                        combined_caption = " / ".join(info["captions"])
                        if not combined_caption.strip():
                            combined_caption = "게시글 내용이 없거나 짧음"
                            
                        profile_link = f"https://instagram.com/{username}"
                        
                        prompt = f'''
                        너는 13년 차 온라인 마케팅 전문가야. 
                        아래 유저가 타겟({brand_target})에 부합하는 진짜 인플루언서인지 정밀하게 판별해.
                        [유저 ID]: {username}
                        [게시글 내용]: {combined_caption}
                        
                        반드시 아래의 정확한 양식으로만 대답해.
                        점수: [0~100 사이 숫자]
                        추천: [YES 또는 NO]
                        요약: [계정이 어떤 특징을 가졌는지 1~2줄로 요약된 핵심 설명]
                        '''
                        
                        score, recommend, bio_summary = "확인불가", "NO", "내용 부족"
                        try:
                            response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                            for line in response.text.strip().split('\n'):
                                line = line.strip()
                                if line.startswith('점수:'): score = line.split(':', 1)[1].strip()
                                elif line.startswith('추천:'): recommend = line.split(':', 1)[1].strip()
                                elif line.startswith('요약:'): bio_summary = line.split(':', 1)[1].strip()
                        except:
                            pass
                        
                        final_list.append({
                            "인스타그램 아이디": username,
                            "이름": info["fullName"],
                            "계정 설명 (AI 요약)": bio_summary,
                            "최근 9개 평균 좋아요": avg_likes_str,
                            "AI 적합도 점수": score,
                            "링크": profile_link
                        })
                        progress_bar.progress((idx + 1) / total_users)

                    df = pd.DataFrame(final_list)
                    st.success("🎉 인플루언서 추출 및 분석 완료! (2단계 탭으로 이동해 섭외 메시지를 만들어보세요)")
                    
                    st.dataframe(
                        df,
                        column_config={"링크": st.column_config.LinkColumn("인스타그램 링크")},
                        hide_index=True,
                        use_container_width=True
                    )
                    
                    csv = df.to_csv(index=False, encoding="utf-8-sig").encode('utf-8-sig')
                    st.download_button("📥 엑셀(CSV) 다운로드", data=csv, file_name=f"추출결과_{search_hashtag}.csv", mime="text/csv")
                    
                except Exception as e:
                    st.error(f"오류 발생: {e}")

# ==========================================
# [탭 2] 듀얼 섭외 메시지 생성기 (친근함 & 비즈니스)
# ==========================================
with tab2:
    col1, col2 = st.columns([1, 1.2]) # 좌측 입력폼, 우측 결과창 비율 조정
    
    with col1:
        st.markdown("### 📝 제안서 정보 입력")
        st.info("1단계에서 추출한 인플루언서의 정보를 바탕으로 맞춤형 메시지를 생성합니다.")
        
        company_name = st.text_input("업체(브랜드)명", placeholder="예: (주)투헬퍼스")
        manager_name = st.text_input("담당자 이름 및 직급", placeholder="예: 홍길동 마케팅 팀장")
        contact_info = st.text_input("회신 받을 연락처 (이메일/오픈카톡 등)", placeholder="예: admin@example.com")
        collab_details = st.text_area("광고/협업 제안 내용", placeholder="예: 신제품 캠핑 의자 협찬 및 릴스 1회 업로드 조건 (고료 10만 원 지급)")
        product_url = st.text_input("상품 또는 브랜드 URL (선택)", placeholder="예: https://tohelpers.co.kr")
        
        st.markdown("---")
        influencer_name = st.text_input("타겟 인플루언서 ID 또는 이름", placeholder="예: baseball_jody")
        influencer_bio = st.text_area("인플루언서 계정 특징 (1단계 AI 요약 복사)", placeholder="예: LG트윈스 찐팬이자 야구장 먹방 직관 브이로그를 주로 올리는 계정")
        
        generate_btn = st.button("✨ 두 가지 버전 메시지 생성", use_container_width=True, type="primary")

    with col2:
        st.markdown("### 💌 AI 맞춤형 제안서 결과")
        if generate_btn:
            if not company_name or not influencer_name or not collab_details:
                st.warning("업체명, 협업 내용, 인플루언서 이름은 필수 입력 항목입니다.")
            else:
                with st.spinner("AI가 인플루언서의 마음을 사로잡을 두 가지 버전의 메시지를 작성 중입니다..."):
                    client = genai.Client(api_key=GEMINI_KEY)
                    
                    # 두 가지 버전을 모두 요구하는 마스터 프롬프트
                    prompt = f"""
                    너는 13년 차 온라인 마케팅 커뮤니케이션 전문가야. 
                    아래 정보를 바탕으로 인플루언서에게 보낼 섭외 DM/메일 초안을 '친근한 버전'과 '정중한 비즈니스 버전' 두 가지로 각각 작성해 줘.

                    [제안 정보]
                    - 업체/브랜드명: {company_name}
                    - 담당자: {manager_name}
                    - 회신 연락처: {contact_info}
                    - 협업 제안 내용: {collab_details}
                    - 상품/브랜드 URL: {product_url}
                    - 타겟 인플루언서: {influencer_name}
                    - 인플루언서 특징: {influencer_bio}

                    [작성 조건]
                    1. 서두에 인플루언서의 특징을 구체적으로 언급하며 진정성 있게 칭찬하고 공감대를 형성할 것.
                    2. 우리 브랜드/상품이 왜 해당 인플루언서와 팬들에게 잘 맞을지 자연스럽게 연결할 것.
                    3. 복사+붙여넣기 한 티가 나지 않도록 매우 자연스럽고 매끄러운 문맥을 사용할 것.
                    4. 반드시 아래 양식에 맞춰 두 가지 버전을 명확히 분리해서 출력할 것.

                    ---
                    ## 💛 친근하고 부드러운 버전
                    (여기에 팬심을 담아 다가가기 쉽고 트렌디한 톤으로 작성. 이모지 적절히 사용.)

                    ## 💼 정중하고 프로페셔널한 비즈니스 버전
                    (여기에 예의를 완벽히 갖추어 신뢰감을 주고 깔끔한 톤으로 작성. 이모지 최소화.)
                    ---
                    """
                    
                    try:
                        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                        st.markdown(response.text)
                        st.success("✅ 생성이 완료되었습니다! 상황에 맞는 버전을 골라 복사해서 사용하세요.")
                    except Exception as e:
                        st.error(f"메시지 생성 중 오류 발생: {e}")
        else:
            st.caption("좌측에 정보를 입력하고 [메시지 생성] 버튼을 누르면 이곳에 결과가 나타납니다.")
