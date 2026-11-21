import { BrowserRouter, Route, Routes, Link } from "react-router";
import { AppShell, Container, RequireRole } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { SessionProvider } from "@/lib/session";
import { ExplorerPage, HomePage, PrivacyPage, PublicCasePage } from "@/pages/public";
import { LoginPage, RegisterPage } from "@/pages/auth";
import { CaseWizard, OwnerCasePage, ReporterDashboard } from "@/pages/reporter";
import { AccountPage, ContributionFormPage, MyContributionsPage } from "@/pages/contributor";
import { EvidenceReviewPage, ReportViewPage, ReportsListPage, ReviewerCasePage, ReviewerDashboard } from "@/pages/reviewer";
import { AdminPage } from "@/pages/admin";

function NotFound() {
  return (
    <Container className="py-24 text-center">
      <h1 className="text-3xl font-bold">Página no encontrada</h1>
      <Button className="mt-6" asChild><Link to="/">Volver al inicio</Link></Button>
    </Container>
  );
}

export default function App() {
  return (
    <SessionProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<HomePage />} />
            <Route path="expedientes" element={<ExplorerPage />} />
            <Route path="expedientes/:code" element={<PublicCasePage />} />
            <Route path="privacidad" element={<PrivacyPage />} />
            <Route path="ingresar" element={<LoginPage />} />
            <Route path="registro" element={<RegisterPage />} />

            <Route element={<RequireRole roles={["DENUNCIANTE", "COLABORADOR"]} />}>
              <Route path="expedientes/:code/aportar" element={<ContributionFormPage />} />
              <Route path="mis-aportaciones" element={<MyContributionsPage />} />
            </Route>
            <Route element={<RequireRole roles={["DENUNCIANTE"]} />}>
              <Route path="mis-expedientes" element={<ReporterDashboard />} />
              <Route path="mis-expedientes/nuevo" element={<CaseWizard />} />
              <Route path="mis-expedientes/:id" element={<OwnerCasePage />} />
              <Route path="mis-expedientes/:id/editar" element={<CaseWizard />} />
            </Route>
            <Route element={<RequireRole roles={["REVISOR"]} />}>
              <Route path="revisor" element={<ReviewerDashboard />} />
              <Route path="revisor/expedientes/:id" element={<ReviewerCasePage />} />
              <Route path="revisor/aportaciones/:id" element={<EvidenceReviewPage />} />
              <Route path="revisor/informes" element={<ReportsListPage />} />
              <Route path="revisor/informes/:id" element={<ReportViewPage />} />
            </Route>
            <Route element={<RequireRole roles={["ADMIN"]} />}>
              <Route path="admin" element={<AdminPage />} />
            </Route>
            <Route element={<RequireRole roles={["DENUNCIANTE", "COLABORADOR", "REVISOR", "ADMIN"]} />}>
              <Route path="cuenta" element={<AccountPage />} />
            </Route>
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </SessionProvider>
  );
}
