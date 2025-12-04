import { desc, and, eq, isNull } from 'drizzle-orm';
import { db } from './drizzle';
import {
  activityLogs,
  teamMembers,
  teams,
  users,
  generatedApplications,
  applicationSessions,
  type NewGeneratedApplication,
  type NewApplicationSession
} from './schema';
import { auth } from '@/auth';

export async function getUser() {
  const session = await auth();

  if (!session?.user?.email) {
    return null;
  }

  // DB에서 사용자 조회 (필요한 컬럼만 선택)
  const [user] = await db
    .select({
      id: users.id,
      name: users.name,
      email: users.email,
      role: users.role,
      createdAt: users.createdAt,
      updatedAt: users.updatedAt,
      deletedAt: users.deletedAt
    })
    .from(users)
    .where(eq(users.email, session.user.email))
    .limit(1);

  return user || null;
}

export async function getTeamByStripeCustomerId(customerId: string) {
  const result = await db
    .select()
    .from(teams)
    .where(eq(teams.stripeCustomerId, customerId))
    .limit(1);

  return result.length > 0 ? result[0] : null;
}

export async function updateTeamSubscription(
  teamId: number,
  subscriptionData: {
    stripeSubscriptionId: string | null;
    stripeProductId: string | null;
    planName: string | null;
    subscriptionStatus: string;
  }
) {
  await db
    .update(teams)
    .set({
      ...subscriptionData,
      updatedAt: new Date()
    })
    .where(eq(teams.id, teamId));
}

export async function getUserWithTeam(userId: number) {
  const result = await db
    .select({
      user: users,
      teamId: teamMembers.teamId
    })
    .from(users)
    .leftJoin(teamMembers, eq(users.id, teamMembers.userId))
    .where(eq(users.id, userId))
    .limit(1);

  return result[0];
}

export async function getActivityLogs() {
  const user = await getUser();
  if (!user) {
    throw new Error('User not authenticated');
  }

  return await db
    .select({
      id: activityLogs.id,
      action: activityLogs.action,
      timestamp: activityLogs.timestamp,
      ipAddress: activityLogs.ipAddress,
      userName: users.name
    })
    .from(activityLogs)
    .leftJoin(users, eq(activityLogs.userId, users.id))
    .where(eq(activityLogs.userId, user.id))
    .orderBy(desc(activityLogs.timestamp))
    .limit(10);
}

export async function getTeamForUser() {
  const user = await getUser();
  if (!user) {
    return null;
  }

  const result = await db.query.teamMembers.findFirst({
    where: eq(teamMembers.userId, user.id),
    with: {
      team: {
        with: {
          teamMembers: {
            with: {
              user: {
                columns: {
                  id: true,
                  name: true,
                  email: true
                }
              }
            }
          }
        }
      }
    }
  });

  return result?.team || null;
}

// ==================== 신청서 생성 관련 쿼리 ====================

/**
 * 신청서 생성 세션 저장
 */
export async function createApplicationSession(
  data: NewApplicationSession
): Promise<{ id: number }> {
  const [result] = await db
    .insert(applicationSessions)
    .values(data)
    .returning({ id: applicationSessions.id });
  return result;
}

/**
 * 생성된 신청서 저장
 */
export async function saveGeneratedApplication(
  data: NewGeneratedApplication
): Promise<{ id: number }> {
  const [result] = await db
    .insert(generatedApplications)
    .values(data)
    .returning({ id: generatedApplications.id });
  return result;
}

/**
 * 여러 신청서 일괄 저장
 */
export async function saveGeneratedApplicationsBatch(
  applications: NewGeneratedApplication[]
): Promise<{ ids: number[] }> {
  const results = await db
    .insert(generatedApplications)
    .values(applications)
    .returning({ id: generatedApplications.id });
  return { ids: results.map(r => r.id) };
}

/**
 * 사용자의 생성된 신청서 목록 조회
 */
export async function getUserGeneratedApplications(
  userId: number,
  limit: number = 50
) {
  return await db
    .select()
    .from(generatedApplications)
    .where(eq(generatedApplications.userId, userId))
    .orderBy(desc(generatedApplications.createdAt))
    .limit(limit);
}

/**
 * 특정 공고에 대한 사용자의 생성된 신청서 조회
 */
export async function getUserApplicationsForAnnouncement(
  userId: number,
  announcementId: string,
  announcementSource: string
) {
  return await db
    .select()
    .from(generatedApplications)
    .where(
      and(
        eq(generatedApplications.userId, userId),
        eq(generatedApplications.announcementId, announcementId),
        eq(generatedApplications.announcementSource, announcementSource)
      )
    )
    .orderBy(desc(generatedApplications.createdAt));
}

/**
 * 신청서 ID로 조회
 */
export async function getGeneratedApplicationById(id: number) {
  const [result] = await db
    .select()
    .from(generatedApplications)
    .where(eq(generatedApplications.id, id))
    .limit(1);
  return result || null;
}

/**
 * 신청서 상태 업데이트
 */
export async function updateApplicationStatus(
  id: number,
  status: string
) {
  await db
    .update(generatedApplications)
    .set({
      status,
      updatedAt: new Date()
    })
    .where(eq(generatedApplications.id, id));
}

/**
 * 신청서 사용자 피드백 업데이트
 */
export async function updateApplicationFeedback(
  id: number,
  feedback: { rating?: number; feedback?: string }
) {
  await db
    .update(generatedApplications)
    .set({
      userRating: feedback.rating,
      userFeedback: feedback.feedback,
      updatedAt: new Date()
    })
    .where(eq(generatedApplications.id, id));
}

/**
 * 사용자의 생성 세션 목록 조회
 */
export async function getUserApplicationSessions(
  userId: number,
  limit: number = 20
) {
  return await db
    .select()
    .from(applicationSessions)
    .where(eq(applicationSessions.userId, userId))
    .orderBy(desc(applicationSessions.createdAt))
    .limit(limit);
}

/**
 * 세션 ID로 세션 및 관련 신청서 조회
 */
export async function getApplicationSessionWithApplications(
  sessionId: number,
  userId: number
) {
  const [session] = await db
    .select()
    .from(applicationSessions)
    .where(
      and(
        eq(applicationSessions.id, sessionId),
        eq(applicationSessions.userId, userId)
      )
    )
    .limit(1);

  if (!session) return null;

  // 해당 세션의 신청서들 조회 (announcementId로 연결)
  const applications = await db
    .select()
    .from(generatedApplications)
    .where(
      and(
        eq(generatedApplications.userId, userId),
        eq(generatedApplications.announcementId, session.announcementId),
        eq(generatedApplications.announcementSource, session.announcementSource)
      )
    )
    .orderBy(generatedApplications.styleRank);

  return { session, applications };
}
