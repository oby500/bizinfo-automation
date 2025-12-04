import {
  pgTable,
  serial,
  varchar,
  text,
  timestamp,
  integer,
  boolean,
} from 'drizzle-orm/pg-core';
import { relations } from 'drizzle-orm';

export const users = pgTable('users', {
  id: serial('id').primaryKey(),
  name: varchar('name', { length: 100 }),
  email: varchar('email', { length: 255 }).notNull().unique(),
  passwordHash: text('password_hash'), // Optional for social login users
  role: varchar('role', { length: 20 }).notNull().default('member'),
  phone: varchar('phone', { length: 20 }), // 전화번호 (알림 시스템용)
  notificationEnabled: boolean('notification_enabled').default(true), // 알림 수신 동의
  createdAt: timestamp('created_at').notNull().defaultNow(),
  updatedAt: timestamp('updated_at').notNull().defaultNow(),
  deletedAt: timestamp('deleted_at'),
});

export const teams = pgTable('teams', {
  id: serial('id').primaryKey(),
  name: varchar('name', { length: 100 }).notNull(),
  createdAt: timestamp('created_at').notNull().defaultNow(),
  updatedAt: timestamp('updated_at').notNull().defaultNow(),
  stripeCustomerId: text('stripe_customer_id').unique(),
  stripeSubscriptionId: text('stripe_subscription_id').unique(),
  stripeProductId: text('stripe_product_id'),
  planName: varchar('plan_name', { length: 50 }),
  subscriptionStatus: varchar('subscription_status', { length: 20 }),
});

export const teamMembers = pgTable('team_members', {
  id: serial('id').primaryKey(),
  userId: integer('user_id')
    .notNull()
    .references(() => users.id),
  teamId: integer('team_id')
    .notNull()
    .references(() => teams.id),
  role: varchar('role', { length: 50 }).notNull(),
  joinedAt: timestamp('joined_at').notNull().defaultNow(),
});

export const activityLogs = pgTable('activity_logs', {
  id: serial('id').primaryKey(),
  teamId: integer('team_id')
    .notNull()
    .references(() => teams.id),
  userId: integer('user_id').references(() => users.id),
  action: text('action').notNull(),
  timestamp: timestamp('timestamp').notNull().defaultNow(),
  ipAddress: varchar('ip_address', { length: 45 }),
});

export const invitations = pgTable('invitations', {
  id: serial('id').primaryKey(),
  teamId: integer('team_id')
    .notNull()
    .references(() => teams.id),
  email: varchar('email', { length: 255 }).notNull(),
  role: varchar('role', { length: 50 }).notNull(),
  invitedBy: integer('invited_by')
    .notNull()
    .references(() => users.id),
  invitedAt: timestamp('invited_at').notNull().defaultNow(),
  status: varchar('status', { length: 20 }).notNull().default('pending'),
});

export const teamsRelations = relations(teams, ({ many }) => ({
  teamMembers: many(teamMembers),
  activityLogs: many(activityLogs),
  invitations: many(invitations),
}));

export const usersRelations = relations(users, ({ many }) => ({
  teamMembers: many(teamMembers),
  invitationsSent: many(invitations),
}));

export const invitationsRelations = relations(invitations, ({ one }) => ({
  team: one(teams, {
    fields: [invitations.teamId],
    references: [teams.id],
  }),
  invitedBy: one(users, {
    fields: [invitations.invitedBy],
    references: [users.id],
  }),
}));

export const teamMembersRelations = relations(teamMembers, ({ one }) => ({
  user: one(users, {
    fields: [teamMembers.userId],
    references: [users.id],
  }),
  team: one(teams, {
    fields: [teamMembers.teamId],
    references: [teams.id],
  }),
}));

export const activityLogsRelations = relations(activityLogs, ({ one }) => ({
  team: one(teams, {
    fields: [activityLogs.teamId],
    references: [teams.id],
  }),
  user: one(users, {
    fields: [activityLogs.userId],
    references: [users.id],
  }),
}));

export type User = typeof users.$inferSelect;
export type NewUser = typeof users.$inferInsert;
export type Team = typeof teams.$inferSelect;
export type NewTeam = typeof teams.$inferInsert;
export type TeamMember = typeof teamMembers.$inferSelect;
export type NewTeamMember = typeof teamMembers.$inferInsert;
export type ActivityLog = typeof activityLogs.$inferSelect;
export type NewActivityLog = typeof activityLogs.$inferInsert;
export type Invitation = typeof invitations.$inferSelect;
export type NewInvitation = typeof invitations.$inferInsert;
export type TeamDataWithMembers = Team & {
  teamMembers: (TeamMember & {
    user: Pick<User, 'id' | 'name' | 'email'>;
  })[];
};

// 결제 내역 테이블
export const payments = pgTable('payments', {
  id: serial('id').primaryKey(),
  userId: integer('user_id')
    .notNull()
    .references(() => users.id),
  paymentId: varchar('payment_id', { length: 255 }).notNull().unique(),
  orderName: varchar('order_name', { length: 255 }).notNull(),
  amount: integer('amount').notNull(), // 실제 결제 금액
  status: varchar('status', { length: 20 }).notNull(), // 'pending', 'paid', 'failed', 'cancelled'
  paymentMethod: varchar('payment_method', { length: 50 }),
  creditAmount: integer('credit_amount'), // 충전 크레딧 (기본)
  bonusAmount: integer('bonus_amount'), // 보너스 크레딧
  totalCredit: integer('total_credit'), // 총 충전 크레딧 (기본 + 보너스)
  paidAt: timestamp('paid_at'),
  createdAt: timestamp('created_at').notNull().defaultNow(),
});

// 크레딧 잔액 테이블
export const credits = pgTable('credits', {
  id: serial('id').primaryKey(),
  userId: integer('user_id')
    .notNull()
    .references(() => users.id)
    .unique(),
  balance: integer('balance').notNull().default(0), // 현재 잔액
  totalCharged: integer('total_charged').notNull().default(0), // 총 충전 금액
  totalUsed: integer('total_used').notNull().default(0), // 총 사용 금액
  updatedAt: timestamp('updated_at').notNull().defaultNow(),
});

// 크레딧 사용 내역 테이블
export const creditTransactions = pgTable('credit_transactions', {
  id: serial('id').primaryKey(),
  userId: integer('user_id')
    .notNull()
    .references(() => users.id),
  paymentId: integer('payment_id').references(() => payments.id), // 충전 시
  type: varchar('type', { length: 20 }).notNull(), // 'charge', 'use', 'refund'
  amount: integer('amount').notNull(), // 양수: 충전/환불, 음수: 사용
  balance: integer('balance').notNull(), // 거래 후 잔액
  description: text('description'),
  createdAt: timestamp('created_at').notNull().defaultNow(),
});

export const paymentsRelations = relations(payments, ({ one, many }) => ({
  user: one(users, {
    fields: [payments.userId],
    references: [users.id],
  }),
  creditTransactions: many(creditTransactions),
}));

export const creditsRelations = relations(credits, ({ one }) => ({
  user: one(users, {
    fields: [credits.userId],
    references: [users.id],
  }),
}));

export const creditTransactionsRelations = relations(creditTransactions, ({ one }) => ({
  user: one(users, {
    fields: [creditTransactions.userId],
    references: [users.id],
  }),
  payment: one(payments, {
    fields: [creditTransactions.paymentId],
    references: [payments.id],
  }),
}));

export type Payment = typeof payments.$inferSelect;
export type NewPayment = typeof payments.$inferInsert;
export type Credit = typeof credits.$inferSelect;
export type NewCredit = typeof credits.$inferInsert;
export type CreditTransaction = typeof creditTransactions.$inferSelect;
export type NewCreditTransaction = typeof creditTransactions.$inferInsert;

// 알림 발송 로그 테이블
export const notificationLogs = pgTable('notification_logs', {
  id: serial('id').primaryKey(),
  userId: integer('user_id')
    .notNull()
    .references(() => users.id),
  type: varchar('type', { length: 50 }).notNull(), // 'payment_success', 'analysis_complete', 'application_generated', 'revision_credit_purchased'
  channel: varchar('channel', { length: 20 }).notNull(), // 'kakao', 'sms'
  status: varchar('status', { length: 20 }).notNull(), // 'sent', 'failed', 'pending'
  phoneNumber: varchar('phone_number', { length: 20 }), // 발송된 전화번호
  messageId: varchar('message_id', { length: 255 }), // 외부 서비스의 메시지 ID
  errorMessage: text('error_message'), // 실패 시 에러 메시지
  metadata: text('metadata'), // JSON 형식의 추가 데이터
  sentAt: timestamp('sent_at'),
  createdAt: timestamp('created_at').notNull().defaultNow(),
});

export const notificationLogsRelations = relations(notificationLogs, ({ one }) => ({
  user: one(users, {
    fields: [notificationLogs.userId],
    references: [users.id],
  }),
}));

export type NotificationLog = typeof notificationLogs.$inferSelect;
export type NewNotificationLog = typeof notificationLogs.$inferInsert;

export enum ActivityType {
  SIGN_UP = 'SIGN_UP',
  SIGN_IN = 'SIGN_IN',
  SIGN_OUT = 'SIGN_OUT',
  UPDATE_PASSWORD = 'UPDATE_PASSWORD',
  DELETE_ACCOUNT = 'DELETE_ACCOUNT',
  UPDATE_ACCOUNT = 'UPDATE_ACCOUNT',
  CREATE_TEAM = 'CREATE_TEAM',
  REMOVE_TEAM_MEMBER = 'REMOVE_TEAM_MEMBER',
  INVITE_TEAM_MEMBER = 'INVITE_TEAM_MEMBER',
  ACCEPT_INVITATION = 'ACCEPT_INVITATION',
}

export enum NotificationType {
  PAYMENT_SUCCESS = 'payment_success',
  REVISION_CREDIT_PURCHASED = 'revision_credit_purchased',
  WRITING_ANALYSIS_COMPLETE = 'writing_analysis_complete',
  APPLICATION_GENERATED = 'application_generated',
}

export enum NotificationChannel {
  KAKAO = 'kakao',
  SMS = 'sms',
}

export enum NotificationStatus {
  PENDING = 'pending',
  SENT = 'sent',
  FAILED = 'failed',
}

// ==================== 챗봇 시스템 테이블 ====================

// 챗봇 대화 세션 테이블
export const chatConversations = pgTable('chat_conversations', {
  id: serial('id').primaryKey(),
  userId: integer('user_id')
    .notNull()
    .references(() => users.id),
  pageContext: varchar('page_context', { length: 100 }), // 'home', 'announcements', 'pricing', 'mypage'
  createdAt: timestamp('created_at').notNull().defaultNow(),
  updatedAt: timestamp('updated_at').notNull().defaultNow(),
});

// 챗봇 메시지 테이블
export const chatMessages = pgTable('chat_messages', {
  id: serial('id').primaryKey(),
  conversationId: integer('conversation_id')
    .notNull()
    .references(() => chatConversations.id),
  role: varchar('role', { length: 20 }).notNull(), // 'user', 'assistant', 'system', 'function'
  content: text('content').notNull(),
  functionName: varchar('function_name', { length: 100 }), // Function calling 사용 시
  functionArgs: text('function_args'), // JSON string
  functionResult: text('function_result'), // JSON string
  createdAt: timestamp('created_at').notNull().defaultNow(),
});

// FAQ 임베딩 테이블 (Vector Store)
export const faqEmbeddings = pgTable('faq_embeddings', {
  id: serial('id').primaryKey(),
  category: varchar('category', { length: 50 }).notNull(), // 'pricing', 'revision', 'service', 'account', 'technical'
  question: text('question').notNull(),
  answer: text('answer').notNull(),
  keywords: text('keywords'), // JSON array string
  embedding: text('embedding'), // JSON array of numbers (vector)
  metadata: text('metadata'), // JSON string (추가 정보)
  createdAt: timestamp('created_at').notNull().defaultNow(),
  updatedAt: timestamp('updated_at').notNull().defaultNow(),
});

// 챗봇 피드백 테이블
export const chatbotFeedback = pgTable('chatbot_feedback', {
  id: serial('id').primaryKey(),
  messageId: integer('message_id')
    .notNull()
    .references(() => chatMessages.id),
  userId: integer('user_id')
    .notNull()
    .references(() => users.id),
  rating: integer('rating'), // 1~5
  feedbackType: varchar('feedback_type', { length: 20 }), // 'helpful', 'not_helpful', 'incorrect', 'irrelevant'
  comment: text('comment'),
  createdAt: timestamp('created_at').notNull().defaultNow(),
});

// Relations
export const chatConversationsRelations = relations(chatConversations, ({ one, many }) => ({
  user: one(users, {
    fields: [chatConversations.userId],
    references: [users.id],
  }),
  messages: many(chatMessages),
}));

export const chatMessagesRelations = relations(chatMessages, ({ one, many }) => ({
  conversation: one(chatConversations, {
    fields: [chatMessages.conversationId],
    references: [chatConversations.id],
  }),
  feedback: many(chatbotFeedback),
}));

export const chatbotFeedbackRelations = relations(chatbotFeedback, ({ one }) => ({
  message: one(chatMessages, {
    fields: [chatbotFeedback.messageId],
    references: [chatMessages.id],
  }),
  user: one(users, {
    fields: [chatbotFeedback.userId],
    references: [users.id],
  }),
}));

// Type exports
export type ChatConversation = typeof chatConversations.$inferSelect;
export type NewChatConversation = typeof chatConversations.$inferInsert;
export type ChatMessage = typeof chatMessages.$inferSelect;
export type NewChatMessage = typeof chatMessages.$inferInsert;
export type FaqEmbedding = typeof faqEmbeddings.$inferSelect;
export type NewFaqEmbedding = typeof faqEmbeddings.$inferInsert;
export type ChatbotFeedback = typeof chatbotFeedback.$inferSelect;
export type NewChatbotFeedback = typeof chatbotFeedback.$inferInsert;

// 챗봇 응답 캐시 테이블
export const chatbotResponseCache = pgTable('chatbot_response_cache', {
  id: serial('id').primaryKey(),
  questionHash: varchar('question_hash', { length: 64 }).notNull().unique(),
  question: text('question').notNull(),
  answer: text('answer').notNull(),
  questionType: varchar('question_type', { length: 20 }).notNull().default('FAQ'), // 'FAQ', 'GENERAL', 'CUSTOM'
  category: varchar('category', { length: 50 }),
  hitCount: integer('hit_count').default(1),
  lastUsedAt: timestamp('last_used_at').notNull().defaultNow(),
  createdAt: timestamp('created_at').notNull().defaultNow(),
  updatedAt: timestamp('updated_at').notNull().defaultNow(),
});

// Type exports
export type ChatbotResponseCache = typeof chatbotResponseCache.$inferSelect;
export type NewChatbotResponseCache = typeof chatbotResponseCache.$inferInsert;

// ==================== 사용자 프로필 테이블 ====================

// 사용자 프로필 테이블 (맞춤형 추천용)
export const userProfiles = pgTable('user_profiles', {
  id: serial('id').primaryKey(),
  userId: integer('user_id')
    .notNull()
    .unique()
    .references(() => users.id),

  // 회사 기본 정보
  companyName: varchar('company_name', { length: 255 }),
  businessNumber: varchar('business_number', { length: 50 }),

  // 산업 분류
  industry: varchar('industry', { length: 100 }),
  subIndustry: varchar('sub_industry', { length: 100 }),
  productService: text('product_service'),

  // 회사 규모
  employeeCount: varchar('employee_count', { length: 50 }),
  annualRevenue: varchar('annual_revenue', { length: 50 }),
  establishmentYear: integer('establishment_year'),
  businessYears: varchar('business_years', { length: 50 }),

  // 지역 정보
  region: varchar('region', { length: 100 }),
  address: text('address'),

  // 사업 특성
  businessType: varchar('business_type', { length: 50 }),
  ventureCertified: boolean('venture_certified').default(false),
  innovativeSme: boolean('innovative_sme').default(false),
  socialEnterprise: boolean('social_enterprise').default(false),

  // 기술 및 R&D
  hasRdDepartment: boolean('has_rd_department').default(false),
  patentCount: integer('patent_count').default(0),
  techCertification: text('tech_certification'),

  // 재무 정보
  creditRating: varchar('credit_rating', { length: 20 }),
  exportExperience: boolean('export_experience').default(false),

  // 관심 분야 (맞춤 추천용)
  interestedFields: text('interested_fields'),
  targetSupportAmount: varchar('target_support_amount', { length: 50 }),

  // ⭐ ApplicationWriter에서 수집하는 필드 (Z - 회사 정보)
  mainProducts: text('main_products'), // 주요 제품/서비스
  targetGoal: text('target_goal'), // 지원 목표
  technology: text('technology'), // 보유 기술
  pastSupport: text('past_support'), // 과거 지원사업 수혜 이력
  additionalInfo: text('additional_info'), // 추가 정보 (동적 필드)

  // 메타데이터
  profileCompleted: boolean('profile_completed').default(false),
  lastUpdatedSource: varchar('last_updated_source', { length: 50 }),

  createdAt: timestamp('created_at').notNull().defaultNow(),
  updatedAt: timestamp('updated_at').notNull().defaultNow(),
});

export const userProfilesRelations = relations(userProfiles, ({ one }) => ({
  user: one(users, {
    fields: [userProfiles.userId],
    references: [users.id],
  }),
}));

export type UserProfile = typeof userProfiles.$inferSelect;
export type NewUserProfile = typeof userProfiles.$inferInsert;

// 환불 테이블
export const refunds = pgTable('refunds', {
  id: serial('id').primaryKey(),
  userId: integer('user_id')
    .notNull()
    .references(() => users.id),
  paymentId: integer('payment_id')
    .notNull()
    .references(() => payments.id),
  portonePaymentId: varchar('portone_payment_id', { length: 255 }).notNull(), // PortOne 결제 ID
  portoneCancellationId: varchar('portone_cancellation_id', { length: 255 }), // PortOne 취소 ID
  requestedAmount: integer('requested_amount').notNull(), // 환불 요청 금액
  refundFee: integer('refund_fee').notNull().default(0), // 환불 수수료
  actualRefundAmount: integer('actual_refund_amount').notNull(), // 실제 환불 금액 (요청금액 - 수수료)
  reason: text('reason'), // 환불 사유
  status: varchar('status', { length: 20 }).notNull().default('pending'), // 'pending', 'completed', 'failed', 'cancelled'
  errorMessage: text('error_message'), // 실패 시 에러 메시지
  completedAt: timestamp('completed_at'), // 환불 완료 시각
  createdAt: timestamp('created_at').notNull().defaultNow(), // 신청 시각
});

export const refundsRelations = relations(refunds, ({ one }) => ({
  user: one(users, {
    fields: [refunds.userId],
    references: [users.id],
  }),
  payment: one(payments, {
    fields: [refunds.paymentId],
    references: [payments.id],
  }),
}));

export type Refund = typeof refunds.$inferSelect;
export type NewRefund = typeof refunds.$inferInsert;

// ==================== 신청서 생성 테이블 ====================

// 생성된 신청서 테이블
export const generatedApplications = pgTable('generated_applications', {
  id: serial('id').primaryKey(),
  userId: integer('user_id')
    .notNull()
    .references(() => users.id),

  // 공고 정보
  announcementId: varchar('announcement_id', { length: 50 }).notNull(),
  announcementSource: varchar('announcement_source', { length: 20 }).notNull(), // 'kstartup' or 'bizinfo'
  announcementTitle: varchar('announcement_title', { length: 500 }),

  // 티어 및 스타일 정보
  tier: varchar('tier', { length: 20 }).notNull(), // 'basic', 'standard', 'premium'
  style: varchar('style', { length: 30 }).notNull(), // 'story', 'data', 'balanced', etc.
  styleName: varchar('style_name', { length: 50 }), // '스토리형', '데이터형', etc.
  styleType: varchar('style_type', { length: 20 }), // 'base' or 'combination'
  styleRank: integer('style_rank'), // 1, 2, 3... (추천 순위)
  isRecommended: boolean('is_recommended').default(false), // AI 라우터 1순위 여부

  // 생성된 콘텐츠
  content: text('content').notNull(), // JSON string - 전체 신청서 내용
  charCount: integer('char_count'), // 글자 수
  sectionCount: integer('section_count'), // 섹션 수

  // AI 메타데이터
  inputTokens: integer('input_tokens'),
  outputTokens: integer('output_tokens'),
  costKrw: integer('cost_krw'), // 비용 (원)
  modelUsed: varchar('model_used', { length: 50 }), // 'claude-sonnet-4-5', etc.

  // 스타일 추천 정보 (AI 라우터 결과 스냅샷)
  styleRecommendation: text('style_recommendation'), // JSON string - 당시 AI 라우터 추천 결과

  // 회사 정보 스냅샷 (생성 시점의 회사 정보)
  companyInfoSnapshot: text('company_info_snapshot'), // JSON string

  // 상태 및 피드백
  status: varchar('status', { length: 20 }).notNull().default('generated'), // 'generated', 'downloaded', 'submitted', 'archived'
  userRating: integer('user_rating'), // 1-5 별점
  userFeedback: text('user_feedback'), // 사용자 피드백

  // 결제 연결
  creditTransactionId: integer('credit_transaction_id')
    .references(() => creditTransactions.id),

  createdAt: timestamp('created_at').notNull().defaultNow(),
  updatedAt: timestamp('updated_at').notNull().defaultNow(),
});

// 신청서 생성 세션 테이블 (한 번의 생성 요청에서 여러 스타일 생성)
export const applicationSessions = pgTable('application_sessions', {
  id: serial('id').primaryKey(),
  userId: integer('user_id')
    .notNull()
    .references(() => users.id),

  // 공고 정보
  announcementId: varchar('announcement_id', { length: 50 }).notNull(),
  announcementSource: varchar('announcement_source', { length: 20 }).notNull(),

  // 세션 정보
  tier: varchar('tier', { length: 20 }).notNull(),
  totalApplications: integer('total_applications').notNull(), // 생성된 총 개수
  totalCostKrw: integer('total_cost_krw'), // 총 비용
  totalTokens: integer('total_tokens'), // 총 토큰

  // AI 라우터 추천 결과
  styleRecommendation: text('style_recommendation'), // JSON string - AI 라우터 추천 결과

  // 선택된 스타일들
  selectedBaseStyles: text('selected_base_styles'), // JSON array ['data', 'professional', 'story']
  selectedCombinationStyles: text('selected_combination_styles'), // JSON array ['expert', 'strategic']

  // 회사 정보 스냅샷
  companyInfoSnapshot: text('company_info_snapshot'), // JSON string

  // 상태
  status: varchar('status', { length: 20 }).notNull().default('completed'), // 'processing', 'completed', 'failed'

  // 결제 연결
  creditTransactionId: integer('credit_transaction_id')
    .references(() => creditTransactions.id),

  createdAt: timestamp('created_at').notNull().defaultNow(),
});

// Relations
export const generatedApplicationsRelations = relations(generatedApplications, ({ one }) => ({
  user: one(users, {
    fields: [generatedApplications.userId],
    references: [users.id],
  }),
  creditTransaction: one(creditTransactions, {
    fields: [generatedApplications.creditTransactionId],
    references: [creditTransactions.id],
  }),
}));

export const applicationSessionsRelations = relations(applicationSessions, ({ one, many }) => ({
  user: one(users, {
    fields: [applicationSessions.userId],
    references: [users.id],
  }),
  creditTransaction: one(creditTransactions, {
    fields: [applicationSessions.creditTransactionId],
    references: [creditTransactions.id],
  }),
}));

// Type exports
export type GeneratedApplication = typeof generatedApplications.$inferSelect;
export type NewGeneratedApplication = typeof generatedApplications.$inferInsert;
export type ApplicationSession = typeof applicationSessions.$inferSelect;
export type NewApplicationSession = typeof applicationSessions.$inferInsert;

// Enums for application system
export enum ApplicationTier {
  BASIC = 'basic',
  STANDARD = 'standard',
  PREMIUM = 'premium',
}

export enum ApplicationStyle {
  // Base styles
  STORY = 'story',
  DATA = 'data',
  AGGRESSIVE = 'aggressive',
  CONSERVATIVE = 'conservative',
  PROFESSIONAL = 'professional',
  // Combination styles
  BALANCED = 'balanced',
  STRATEGIC = 'strategic',
  TRUSTED = 'trusted',
  EXPERT = 'expert',
}

export enum ApplicationStatus {
  GENERATED = 'generated',
  DOWNLOADED = 'downloaded',
  SUBMITTED = 'submitted',
  ARCHIVED = 'archived',
}
