import React, { useState, useEffect } from "react";
import Image from "next/image";
import { useRouter } from "next/router";

interface Message {
  sender: string;
  text: string;
}

const Chatbot = () => {
  const [input, setInput] = useState<string>("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const router = useRouter();

  const API_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:20005";

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

    // 추천된 강의 불러오기
    const savedCourses = localStorage.getItem("recommendedCourses");
    if (savedCourses) {
      const courseData = JSON.parse(savedCourses);
      const formattedCourses = courseData["추천 강의"]
        ? courseData["추천 강의"]
            .map((course: any) => `📚 ${course.강의명} (${course.교수님}) - ${course.요일} ${course.교시}`)
            .join("\n")
        : "추천할 강의가 없습니다.";

      setMessages((prev) => [
        ...prev,
        { sender: "bot", text: "추천된 강의 목록:\n" + formattedCourses },
      ]);

      localStorage.removeItem("recommendedCourses"); //중복 방지
    }
  }, []);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setInput(e.target.value);
  };

  const handleSend = async () => {
    if (input.trim()) {
      await sendTextQuery(input);
    }
  };

  const sendTextQuery = async (query: string) => {
    const userMessage = { sender: "user", text: query };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    const botLoadingMessage = { sender: "bot", text: "답변을 생성 중입니다..." };
    setMessages((prev) => [...prev, botLoadingMessage]);

    try {
      const response = await fetch(`${API_URL}/api/chat/`, {
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

  return (
    <div style={{
      display: "flex",
      justifyContent: "center",
      alignItems: "center",
      flexDirection: "column",
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
        textAlign: "center",
      }}>
        <h1 style={{ color: "#8B3A3A", fontSize: "24px", fontWeight: "bold" }}>
          광운대 전자공학과 챗봇
        </h1>

        <div style={{
          marginBottom: "15px",
          height: "300px",
          overflowY: "auto",
          border: "1px solid #ddd",
          padding: "10px",
          borderRadius: "10px",
          backgroundColor: "#F9F9F9",
        }}>
          {messages.map((msg, index) => (
            <div key={index} style={{
              marginBottom: "10px",
              padding: "10px",
              borderRadius: "8px",
              backgroundColor: msg.sender === "user" ? "#FFD700" : "#F0F0F0",
              textAlign: msg.sender === "user" ? "right" : "left",
            }}>
              <strong>{msg.sender === "user" ? "사용자" : "챗봇"}:</strong> {msg.text}
            </div>
          ))}
        </div>

        {/* 메인 페이지로 돌아가는 버튼 */}
        <button
          onClick={() => router.push("/")}  // 메인 페이지로 이동
          style={{
            backgroundColor: "#8B3A3A",
            color: "#fff",
            padding: "10px 20px",
            borderRadius: "10px",
            border: "none",
            cursor: "pointer",
            fontSize: "16px",
            marginTop: "10px",
            transition: "0.3s",
          }}
        >
          ↩ 메인 페이지로 돌아가기
        </button>

        {/* 학교 로고 추가 */}
        <div style={{ marginTop: "20px" }}>
          <Image 
            src="/images/logo2.png" 
            alt="광운대학교 로고"
            width={180}
            height={40}
            priority
          />
        </div>
      </div>
    </div>
  );
};

export default Chatbot;
