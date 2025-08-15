"use client";
import React, { useState, useEffect } from "react";
import Image from "next/image";

interface Message {
  sender: string;
  text: string;
}

const Chatbot = () => {
  const [input, setInput] = useState<string>("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedTimes, setSelectedTimes] = useState<{ day: string; time: string }[]>([]); // 수동 시간 선택 추가

  const API_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://223.194.8.50:20005"; // 변경됨

  // 기존 대화 기록 불러오기
  useEffect(() => {
    fetch(`${API_URL}/api/chat/history`)
      .then((res) => res.json())
      .then((data) => {
        if (data.chat_history) {
          setMessages(
            data.chat_history.flatMap((msg: any) => [
              { sender: "user", text: msg.user },
              { sender: "bot", text: msg.bot },
            ])
          );
        }
      })
      .catch(() => console.warn("대화 기록을 불러오지 못했습니다."));
  }, []);

  // 텍스트 입력 핸들러
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setInput(e.target.value);
  };

  // 이미지 선택 핸들러
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setSelectedFile(e.target.files[0]);
    }
  };

  // 시간 선택 페이지 이동 (UI 추가 예정)
  const handleTimeSelection = () => {
    window.location.href = "/time-selection"; // 시간 선택 페이지로 이동
  };

  // 텍스트 질의 전송
  const handleSend = async () => {
    if (input.trim()) {
      await sendTextQuery(input);
    }
  };

  // 텍스트 질의 API 요청
  const sendTextQuery = async (query: string) => {
    const userMessage = { sender: "user", text: query };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    const botLoadingMessage = { sender: "bot", text: "⏳ 답변을 생성 중입니다..." };
    setMessages((prev) => [...prev, botLoadingMessage]);

    try {
      const response = await fetch(`${API_URL}/api/chat/`, { //변경
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });

      if (!response.ok) throw new Error("서버 응답 오류");

      const data = await response.json();
      const botResponse = { sender: "bot", text: data.response };

      setMessages((prevMessages) => prevMessages.slice(0, -1).concat(botResponse));
    } catch (error) {
      setMessages((prevMessages) =>
        prevMessages.slice(0, -1).concat({ sender: "bot", text: "서버 오류 발생" })
      );
    } finally {
      setLoading(false);
    }
  };

  // 시간 선택 후 강의 추천 요청 (기능 추가)
  const sendManualTimeQuery = async () => {
    if (selectedTimes.length === 0) {
      setMessages((prev) => [...prev, { sender: "bot", text: "선택된 시간이 없습니다." }]);
      return;
    }

    const userMessage = { sender: "user", text: "수동 시간 선택 완료" };
    setMessages((prev) => [...prev, userMessage]);
    setLoading(true);

    try {
      const response = await fetch(`${API_URL}/api/recommend/manual`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ available_times: selectedTimes }),
      });

      if (!response.ok) throw new Error("시간 선택 강의 추천 오류");

      const data = await response.json();
      const recommendedCourses = data["추천 강의"] || [];

      let recommendedText =
        recommendedCourses.length > 0
          ? `추천 강의:\n${recommendedCourses
              .map((course: { 요일: string; 교시: string; 강의명: string; 교수님: string }) => 
                `✔ ${course.요일} ${course.교시}: ${course.강의명} (${course.교수님})`)
              .join("\n")}`
          : "추천할 강의가 없습니다.";

      setMessages((prevMessages) => prevMessages.concat({ sender: "bot", text: recommendedText }));
    } catch (error) {
      setMessages((prevMessages) =>
        prevMessages.concat({ sender: "bot", text: "강의 추천 오류 발생" })
      );
    } finally {
      setLoading(false);
    }
  };

  // 이미지 업로드 후 시간표 분석 + 강의 추천 (기존 코드 유지)
  const sendImageQuery = async () => {
    if (!selectedFile) return;

    const formData = new FormData();
    formData.append("file", selectedFile);

    const userMessage = { sender: "user", text: "📷 이미지 업로드 완료" };
    setMessages((prev) => [...prev, userMessage]);
    setSelectedFile(null);
    setLoading(true);

    try {
      const imageResponse = await fetch(`${API_URL}/api/image/detect_empty_slots`, {
        method: "POST",
        body: formData,
      });

      if (!imageResponse.ok) throw new Error("이미지 처리 오류");

      const imageData = await imageResponse.json();
      console.log("백엔드 응답 데이터:", imageData);
      console.log("감지된 빈 시간 데이터 (free_slots):", JSON.stringify(imageData.free_slots, null, 2));

      const freeSlots: Record<string, string[]> = imageData.free_slots || {};
      console.log("변환된 freeSlots 데이터:", JSON.stringify(freeSlots, null, 2));

      let freeText = "감지된 빈 시간:\n";
      if (!freeSlots || Object.keys(freeSlots).length === 0) {
        freeText += "감지된 빈 시간이 없습니다.\n";
      } else {
        freeText += Object.entries(freeSlots)
          .map(([day, times]) => `📅 ${day}: ${times.length > 0 ? times.join(", ") : "없음"}`)
          .join("\n");
      }

      const recommendResponse = await fetch(`${API_URL}/api/recommend/`, { 
        method: "POST",
        body: formData,
      });

      if (!recommendResponse.ok) throw new Error("강의 추천 오류");

      const recommendData = await recommendResponse.json();
      const recommendedCourses = recommendData["추천 강의"] || [];

      let recommendedText =
        recommendedCourses.length > 0
          ? `추천 강의:\n${recommendedCourses
              .map((course: { 시간: string; 강의명: string; 교수님: string }) => 
                `✔ [${course.시간}] : ${course.강의명}(${course.교수님})`)
              .join("\n")}`
          : "추천할 강의가 없습니다.";

      setMessages((prevMessages) =>
        prevMessages.slice(0, -1).concat({ sender: "bot", text: `${freeText}\n\n${recommendedText}` })
      );
    } catch (error) {
      setMessages((prevMessages) =>
        prevMessages.slice(0, -1).concat({ sender: "bot", text: "❌ 이미지 처리 오류 발생" })
      );
    } finally {
      setLoading(false);
    }
  };

  // 대화 기록 초기화 (백엔드 히스토리도 삭제)
  const handleResetChat = async () => {
    try {
      await fetch(`${API_URL}/api/chat/reset_chat`, { method: "POST" });
      setMessages([]);
    } catch (error) {
      console.error("대화 초기화 실패:", error);
    }
  };

  return (
    <div style={{
      display: "flex",
      justifyContent: "center",
      alignItems: "center",
      minHeight: "100vh",
      background: "linear-gradient(135deg, #8B3A3A, #A0522D)",
      fontFamily: "Arial, sans-serif",
      color: "#333",
    }}>
      <div style={{
        backgroundColor: "#ffffff",
        padding: "30px",
        borderRadius: "20px",
        boxShadow: "0 10px 30px rgba(0, 0, 0, 0.1)",
        width: "100%",
        maxWidth: "500px",
      }}>
        <h1 style={{ textAlign: "center", color: "#8B3A3A", fontSize: "24px", fontWeight: "bold" }}>
          광운대 전자공학과 챗봇
        </h1>
  
        <div style={{ marginBottom: "15px", height: "300px", overflowY: "auto", border: "1px solid #ddd", padding: "10px", borderRadius: "10px" }}>
          {messages.map((msg, index) => (
            <div key={index} style={{
              marginBottom: "10px",
              padding: "10px",
              borderRadius: "8px",
              backgroundColor: msg.sender === "user" ? "#FFD700" : "#F0F0F0",
              textAlign: msg.sender === "user" ? "right" : "left",
              whiteSpace: "pre-line", //줄바꿈 적용
            }}>
              <strong>{msg.sender === "user" ? "👤 사용자" : "🤖 챗봇"}:</strong> {msg.text}
            </div>
          ))}
        </div>
  
        <input 
          type="text"
          value={input}
          onChange={handleInputChange}
          onKeyDown={(e) =>{
            if (e.key === "Enter" && !loading){
              handleSend();
            }
          }}
          placeholder="질문을 입력하세요..." 
          style={{ width: "96%", padding: "10px", borderRadius: "8px", border: "1px solid #bbb", marginBottom: "10px" }} 
        />
  
        {/* 파일 선택 & 시간 선택 버튼 정렬 수정 */}
        <div style={{ display: "flex", justifyContent: "center", width: "100%", marginBottom: "10px", gap: "10px" }}>
          
          {/* 파일 선택 버튼 */}
          <label 
            htmlFor="file-upload" 
            style={{
              flex: 1,  //버튼 크기 균일화
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: "10px",
              borderRadius: "8px",
              backgroundColor: "#F5F5F5",
              color: "#333",
              cursor: "pointer",
              textAlign: "center",
              border: "1px solid #bbb",
              fontSize: "16px",
              fontWeight: "bold",
              transition: "background 0.3s ease",
              width: "50%",  //크기 강제 조정
            }}
            onMouseEnter={(e) => e.currentTarget.style.backgroundColor = "#E0E0E0"}
            onMouseLeave={(e) => e.currentTarget.style.backgroundColor = "#F5F5F5"}
          >
            파일 선택
          </label>
          <input 
            id="file-upload" 
            type="file" 
            accept="image/*" 
            onChange={handleFileChange} 
            style={{ display: "none" }} 
          />
  
          {/* 시간 선택 버튼 */}
          <button 
            onClick={() => window.location.href = "/time-selection"} 
            style={{ 
              flex: 1,  // 동일한 크기로 유지
              padding: "10px",
              borderRadius: "8px",
              backgroundColor: "#8B3A3A",
              color: "#fff",
              cursor: "pointer",
              border: "1px solid #bbb",
              fontSize: "16px",
              fontWeight: "bold",
              transition: "background 0.3s ease",
              width: "50%",  // 크기 강제 조정
            }}
            onMouseEnter={(e) => e.currentTarget.style.backgroundColor = "#732D2D"}
            onMouseLeave={(e) => e.currentTarget.style.backgroundColor = "#8B3A3A"}
          >
            시간 선택하기
          </button>
        </div>
        
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          {/* 질문 보내기 버튼 */}
          <button 
            onClick={handleSend} 
            disabled={loading} 
            style={{ 
              flex: 1, margin: "0 5px", padding: "10px", borderRadius: "8px", 
              backgroundColor: "#8B3A3A", color: "#fff", cursor: "pointer", border: "none",
              transition: "background 0.3s ease"
            }}
            onMouseEnter={(e) => e.currentTarget.style.backgroundColor = "#732D2D"}
            onMouseLeave={(e) => e.currentTarget.style.backgroundColor = "#8B3A3A"}
          >
            질문 보내기
          </button>
  
          {/* 이미지 업로드 버튼 */}
          <button 
            onClick={sendImageQuery} 
            disabled={loading || !selectedFile} 
            style={{ 
              flex: 1, margin: "0 5px", padding: "10px", borderRadius: "8px", 
              backgroundColor: "#8B3A3A", color: "#fff", cursor: "pointer", border: "none",
              transition: "background 0.3s ease"
            }}
            onMouseEnter={(e) => e.currentTarget.style.backgroundColor = "#732D2D"}
            onMouseLeave={(e) => e.currentTarget.style.backgroundColor = "#8B3A3A"}
          >
            이미지 업로드
          </button>
  
          {/* 대화 초기화 버튼 */}
          <button 
            onClick={handleResetChat} 
            disabled={loading} 
            style={{ 
              flex: 1, margin: "0 5px", padding: "10px", borderRadius: "8px", 
              backgroundColor: "#B22222", color: "#fff", cursor: "pointer", border: "none",
              transition: "background 0.3s ease"
            }}
            onMouseEnter={(e) => e.currentTarget.style.backgroundColor = "#8B0000"}
            onMouseLeave={(e) => e.currentTarget.style.backgroundColor = "#B22222"}
          >
            대화 초기화
          </button>
        </div>
  
        {/* 로고 추가 (하단 중앙 정렬) */}
        <div style={{ textAlign: "center", transform: "translateY(20px)", paddingTop: "10px", paddingBottom: "10px" }}>
          <Image src="/images/logo2.png" alt="광운대학교 로고" width={180} height={40} />
        </div>
      </div>
    </div>
  );
}

export default Chatbot;
