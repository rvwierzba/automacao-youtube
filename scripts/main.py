// Program.cs

using Microsoft.EntityFrameworkCore;
using Npgsql.EntityFrameworkCore.PostgreSQL;
using System.Net.Http;
using System.Text.Json;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Configuration;
using Microsoft.AspNetCore.Identity;
using Microsoft.AspNetCore.Identity.EntityFrameworkCore;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.IdentityModel.Tokens;
using System.Text;
using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using Backend.Models;
using Backend.Data;
using System.Collections.Generic;
using System.Linq;
using System;
using Microsoft.AspNetCore.Authorization;
using Backend.Services;
using Backend.Models.Requests;
using Backend.Models.Plans;
using Backend.Models.Responses; // Using para LoginResponse
using Stripe;
using Stripe.Checkout;
using Microsoft.OpenApi.Models;
using Microsoft.Extensions.Logging;
using Microsoft.AspNetCore.Http; // Para StatusCodes e HttpContext

var builder = WebApplication.CreateBuilder(args);

var stripeSecretKey = builder.Configuration["Stripe:SecretKey"];
if (string.IsNullOrEmpty(stripeSecretKey)) { throw new InvalidOperationException("Chave secreta do Stripe (Stripe:SecretKey) não configurada."); }
StripeConfiguration.ApiKey = stripeSecretKey;

// --- Configuração dos Serviços ---
builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen(options =>
{
    options.SwaggerDoc("v1", new OpenApiInfo { Version = "v1", Title = "AIketing API", Description = "API para o serviço AIketing SaaS" });
    options.AddSecurityDefinition("Bearer", new OpenApiSecurityScheme { In = ParameterLocation.Header, Description = "Insira 'Bearer' [espaço] e o token JWT. Ex: Bearer ey...", Name = "Authorization", Type = SecuritySchemeType.Http, BearerFormat = "JWT", Scheme = "Bearer" }); // Type = Http
    options.AddSecurityRequirement(new OpenApiSecurityRequirement { { new OpenApiSecurityScheme { Reference = new OpenApiReference { Type = ReferenceType.SecurityScheme, Id = "Bearer" } }, new List<string>() } });
});

var connectionString = builder.Configuration.GetConnectionString("DefaultConnection");
builder.Services.AddDbContext<ApplicationDbContext>(options =>
    options.UseNpgsql(connectionString));

builder.Services.AddIdentity<User, IdentityRole>(options =>
    {
        options.SignIn.RequireConfirmedAccount = false;
        options.Password.RequireDigit = true;
        options.Password.RequireLowercase = true;
        options.Password.RequireUppercase = true;
        options.Password.RequireNonAlphanumeric = true;
        options.Password.RequiredLength = 8;
        options.Lockout.DefaultLockoutTimeSpan = TimeSpan.FromMinutes(5);
        options.Lockout.MaxFailedAccessAttempts = 5;
        options.User.RequireUniqueEmail = true;
    })
    .AddEntityFrameworkStores<ApplicationDbContext>()
    .AddDefaultTokenProviders();

builder.Services.AddAuthentication(options =>
    {
        options.DefaultAuthenticateScheme = JwtBearerDefaults.AuthenticationScheme;
        options.DefaultChallengeScheme = JwtBearerDefaults.AuthenticationScheme;
    })
    .AddJwtBearer(options =>
    {
        options.TokenValidationParameters = new TokenValidationParameters
        {
            ValidateIssuerSigningKey = true,
            IssuerSigningKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(builder.Configuration["Jwt:Key"] ?? throw new InvalidOperationException("Jwt:Key not configured"))),
            ValidateIssuer = true,
            ValidIssuer = builder.Configuration["Jwt:Issuer"] ?? throw new InvalidOperationException("Jwt:Issuer not configured"), // Deve ser http://localhost:5235
            ValidateAudience = true,
            ValidAudience = builder.Configuration["Jwt:Audience"] ?? throw new InvalidOperationException("Jwt:Audience not configured"), // Deve ser http://localhost:5235
            ValidateLifetime = true,
            ClockSkew = TimeSpan.Zero
        };
    });

builder.Services.AddHttpClient();
builder.Services.AddScoped<IGeradorTextoService, GeradorTextoServiceLocalOllama>();
builder.Services.AddScoped<IGeradorImagemService, GeradorImagemServiceApiExterna>();
builder.Services.AddScoped<Backend.Services.IPlanService, Backend.Services.PlanService>();

if (builder.Environment.IsDevelopment())
{
    builder.Services.AddCors(options =>
    {
        options.AddPolicy("AllowAll", policy =>
        {
            policy.AllowAnyOrigin()
                  .AllowAnyMethod()
                  .AllowAnyHeader();
        });
    });
}

var app = builder.Build();

if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI(c => { c.SwaggerEndpoint("/swagger/v1/swagger.json", "AIketing API v1"); });
    app.UseCors("AllowAll");
    app.UseDeveloperExceptionPage();
}
else
{
    app.UseExceptionHandler("/error"); // Endpoint de erro genérico
    app.UseHsts();
}

// Endpoint de erro genérico (exemplo)
app.MapGet("/error", () => Results.Problem("Ocorreu um erro inesperado.", statusCode: 500)).ExcludeFromDescription();


app.UseHttpsRedirection();
app.UseAuthentication();
app.UseAuthorization();

// --- ENDPOINTS (COM IMPLEMENTAÇÕES COMPLETAS) ---

app.MapGet("/generate-test", async (
    IGeradorTextoService generator,
    UserManager<User> userManager,
    ApplicationDbContext dbContext,
    Backend.Services.IPlanService planService,
    ClaimsPrincipal userPrincipal,
    ILogger<Program> logger,
    [FromQuery] string prompt,
    [FromQuery] string? modelName
    ) => {
        logger.LogInformation("Executando /generate-test...");
        if (string.IsNullOrWhiteSpace(prompt)) return Results.BadRequest("O parâmetro 'prompt' é obrigatório.");
        var userId = userManager.GetUserId(userPrincipal);
        if (userId == null) return Results.Unauthorized();
        var user = await userManager.Users.FirstOrDefaultAsync(u => u.Id == userId);
        if (user == null) return Results.NotFound("Usuário não encontrado.");
        if (string.IsNullOrEmpty(user.CurrentPlanName) || user.SubscriptionCycleStart == default)
        {
             user.CurrentPlanName ??= "Free";
             if (user.SubscriptionCycleStart == default) { user.SubscriptionCycleStart = new DateTime(DateTime.UtcNow.Year, DateTime.UtcNow.Month, 1, 0, 0, 0, DateTimeKind.Utc); } // Garantir UTC
             await userManager.UpdateAsync(user);
        }
        var planDetails = planService.GetPlanDetails(user.CurrentPlanName) ?? planService.GetDefaultPlan();
        var cycleStartDate = user.SubscriptionCycleStart == DateTime.MinValue ? new DateTime(DateTime.UtcNow.Year, DateTime.UtcNow.Month, 1, 0, 0, 0, DateTimeKind.Utc) : user.SubscriptionCycleStart; // Garantir UTC
        var nextCycleStartDate = cycleStartDate.AddMonths(1);
        var textGenerationsThisCycle = await dbContext.GenerationHistory.CountAsync(h => h.UserId == userId && h.ContentType == "Text" && h.Timestamp >= cycleStartDate && h.Timestamp < nextCycleStartDate);
        if (textGenerationsThisCycle >= planDetails.TextGenerationsLimit)
        {
            logger.LogWarning("[GenerateTest Endpoint] Limite atingido para {UserId} no plano {PlanName}", userId, planDetails.DisplayName);
            return Results.Json(new { message = $"Você atingiu o limite de {planDetails.TextGenerationsLimit} gerações de texto para este mês no seu plano {planDetails.DisplayName}." }, statusCode: StatusCodes.Status429TooManyRequests);
        }
        var modelToUse = string.IsNullOrWhiteSpace(modelName) ? "tinyllama" : modelName;
        logger.LogInformation("[GenerateTest Endpoint] Usuário {UserId} (Plano: {PlanName}, Usado: {Used}/{Limit} textos) solicitou geração. Prompt: '{Prompt}'", userId, planDetails.DisplayName, textGenerationsThisCycle, planDetails.TextGenerationsLimit, prompt);
        var generatedText = await generator.GenerateTextAsync(prompt, modelToUse);
        var historyEntry = new GenerationHistory { UserId = userId, Timestamp = DateTime.UtcNow, ContentType = "Text", InputPrompt = prompt, OutputText = generatedText, ModelUsed = modelToUse };
        try { dbContext.GenerationHistory.Add(historyEntry); await dbContext.SaveChangesAsync(); } catch (Exception ex) { logger.LogError(ex, "Falha ao salvar histórico texto para {UserId}", userId); }
        return Results.Ok(new { prompt, model = modelToUse, generatedText, historyId = historyEntry.Id });
    })
    .WithName("GenerateTextTest").WithOpenApi().RequireAuthorization();

app.MapGet("/generate-image-test", async (
    IGeradorImagemService imageGenerator,
    UserManager<User> userManager,
    ApplicationDbContext dbContext,
    Backend.Services.IPlanService planService,
    ClaimsPrincipal userPrincipal,
    ILogger<Program> logger,
    [FromQuery] string prompt,
    [FromQuery] string style = "digital art"
    ) => {
    logger.LogInformation("Executando /generate-image-test...");
    if (string.IsNullOrWhiteSpace(prompt)) return Results.BadRequest("O parâmetro 'prompt' é obrigatório.");
    var userId = userManager.GetUserId(userPrincipal);
    if (userId == null) return Results.Unauthorized();
    var user = await userManager.Users.FirstOrDefaultAsync(u => u.Id == userId);
    if (user == null) return Results.NotFound("Usuário não encontrado.");
    if (string.IsNullOrEmpty(user.CurrentPlanName) || user.SubscriptionCycleStart == default)
    {
        user.CurrentPlanName ??= "Free";
        if (user.SubscriptionCycleStart == default) { user.SubscriptionCycleStart = new DateTime(DateTime.UtcNow.Year, DateTime.UtcNow.Month, 1, 0, 0, 0, DateTimeKind.Utc); } // Garantir UTC
        await userManager.UpdateAsync(user);
    }
    var planDetails = planService.GetPlanDetails(user.CurrentPlanName) ?? planService.GetDefaultPlan();
    var cycleStartDate = user.SubscriptionCycleStart == DateTime.MinValue ? new DateTime(DateTime.UtcNow.Year, DateTime.UtcNow.Month, 1, 0, 0, 0, DateTimeKind.Utc) : user.SubscriptionCycleStart; // Garantir UTC
    var nextCycleStartDate = cycleStartDate.AddMonths(1);
    var thumbnailGenerationsThisCycle = await dbContext.GenerationHistory.CountAsync(h => h.UserId == userId && h.ContentType == "Image" && h.Timestamp >= cycleStartDate && h.Timestamp < nextCycleStartDate);
    if (thumbnailGenerationsThisCycle >= planDetails.ThumbnailGenerationsLimit)
    {
        logger.LogWarning("[GenerateImageTest Endpoint] Limite atingido para {UserId} no plano {PlanName}", userId, planDetails.DisplayName);
        return Results.Json(new { message = $"Você atingiu o limite de {planDetails.ThumbnailGenerationsLimit} gerações de thumbnail para este mês no seu plano {planDetails.DisplayName}." }, statusCode: StatusCodes.Status429TooManyRequests);
    }
    var width = 512; var height = 512;
    logger.LogInformation("[GenerateImageTest Endpoint] Usuário {UserId} (Plano: {PlanName}, Usado: {Used}/{Limit} thumbnails) solicitou geração. Prompt: '{Prompt}'", userId, planDetails.DisplayName, thumbnailGenerationsThisCycle, planDetails.ThumbnailGenerationsLimit, prompt);
    var base64Images = await imageGenerator.GenerateImageAsync(prompt, style, width, height);
    var firstImageBase64 = base64Images.FirstOrDefault();
    var historyEntry = new GenerationHistory { UserId = userId, Timestamp = DateTime.UtcNow, ContentType = "Image", InputPrompt = prompt, OutputImageBase64 = firstImageBase64, ModelUsed = "black-forest-labs/FLUX.1-dev" };
    if (!string.IsNullOrEmpty(firstImageBase64)) { try { dbContext.GenerationHistory.Add(historyEntry); await dbContext.SaveChangesAsync(); } catch (Exception ex) { logger.LogError(ex, "Falha ao salvar histórico imagem para {UserId}", userId); } }
    return Results.Ok(new { prompt, style, width, height, base64Images, historyId = historyEntry.Id > 0 ? historyEntry.Id : (int?)null });
})
.WithName("GenerateImageTest").WithOpenApi().RequireAuthorization();

app.MapPost("/api/auth/register", async (
    [FromBody] RegisterRequest request,
    UserManager<User> userManager,
    ILogger<Program> logger
    ) =>
{
    logger.LogInformation("Executando /api/auth/register para {Email}...", request.Email);
    if (string.IsNullOrEmpty(request.Email) || string.IsNullOrEmpty(request.Password)) return Results.BadRequest(new { message = "Email e senha são obrigatórios." });
    var user = new User { UserName = request.Email, Email = request.Email }; // CreatedAt é UTC por padrão
    var result = await userManager.CreateAsync(user, request.Password);
    if (result.Succeeded) {
        logger.LogInformation("Usuário {Email} criado com sucesso. Atualizando plano/ciclo...", user.Email);
        user.CurrentPlanName = "Free";
        user.SubscriptionCycleStart = new DateTime(DateTime.UtcNow.Year, DateTime.UtcNow.Month, 1, 0, 0, 0, DateTimeKind.Utc); // UTC
        var updateResult = await userManager.UpdateAsync(user);
        if (!updateResult.Succeeded) { logger.LogError("Falha ao atualizar usuário {Email} após registro com plano/ciclo: {Errors}", user.Email, string.Join(", ", updateResult.Errors.Select(e => e.Description))); }
        else { logger.LogInformation("Usuário {Email} atualizado com plano Free e ciclo.", user.Email); }
        return Results.Ok(new { message = "Usuário registrado com sucesso!" });
    }
    else
    {
        logger.LogWarning("Falha no registro para {Email}: {Errors}", request.Email, string.Join(", ", result.Errors.Select(e => e.Description)));
        return Results.BadRequest(new { errors = result.Errors.Select(e => e.Description) });
    }
})
.WithName("Register").WithOpenApi();

app.MapPost("/api/auth/login", async (
    [FromBody] LoginRequest request,
    UserManager<User> userManager,
    SignInManager<User> signInManager,
    IConfiguration configuration,
    ILogger<Program> logger
    ) =>
{
    logger.LogInformation("[Login Endpoint] Tentativa de login para: {Email}", request.Email);
    if (string.IsNullOrEmpty(request.Email) || string.IsNullOrEmpty(request.Password)) { logger.LogWarning("[Login Endpoint] Falha: Email ou senha não fornecidos."); return Results.BadRequest(new { message = "Email e senha são obrigatórios." }); }

    var user = await userManager.FindByEmailAsync(request.Email);
    if (user == null) { logger.LogWarning("[Login Endpoint] Falha: Usuário não encontrado para {Email}", request.Email); return Results.Unauthorized(); }

    var result = await signInManager.CheckPasswordSignInAsync(user, request.Password, lockoutOnFailure: true);
    if (result.Succeeded)
    {
        logger.LogInformation("[Login Endpoint] Login bem-sucedido para: {Email}. Gerando token...", user.Email);
        var authClaims = new List<Claim> { new Claim(ClaimTypes.NameIdentifier, user.Id), new Claim(ClaimTypes.Email, user.Email!), new Claim(JwtRegisteredClaimNames.Jti, Guid.NewGuid().ToString()) };
        var jwtKey = configuration["Jwt:Key"]!; var issuer = configuration["Jwt:Issuer"]!; var audience = configuration["Jwt:Audience"]!;
        var authSigningKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(jwtKey));
        var token = new JwtSecurityToken(issuer: issuer, audience: audience, expires: DateTime.Now.AddHours(24), claims: authClaims, signingCredentials: new SigningCredentials(authSigningKey, SecurityAlgorithms.HmacSha256));
        var tokenString = new JwtSecurityTokenHandler().WriteToken(token);

        var responseObject = new LoginResponse { Token = tokenString, Expiration = token.ValidTo, UserId = user.Id, Email = user.Email ?? string.Empty };

        logger.LogInformation("[Login Endpoint] Token gerado (início): {TokenStart}...", tokenString.Substring(0, Math.Min(tokenString.Length, 10)));
        logger.LogInformation("[Login Endpoint] Objeto de resposta DTO preparado: UserId={UserId}, Email={Email}", responseObject.UserId, responseObject.Email);
        logger.LogInformation("[Login Endpoint] Retornando Results.Ok com o objeto DTO...");

        return Results.Ok(responseObject); // Usando Results.Ok com o DTO
    }

    if (result.IsLockedOut) { logger.LogWarning("[Login Endpoint] Falha: Usuário bloqueado: {Email}", user.Email); return Results.StatusCode(StatusCodes.Status423Locked); }
    if (result.IsNotAllowed) { logger.LogWarning("[Login Endpoint] Falha: Usuário não permitido: {Email}", user.Email); return Results.Unauthorized(); }
    if (result.RequiresTwoFactor) { logger.LogWarning("[Login Endpoint] Falha: Requer 2FA: {Email}", user.Email); return Results.Unauthorized(); }

    logger.LogWarning("[Login Endpoint] Falha: Credenciais inválidas para {Email}", request.Email);
    return Results.Unauthorized();
})
.WithName("Login").WithOpenApi()
.Produces<LoginResponse>(StatusCodes.Status200OK)
.Produces(StatusCodes.Status400BadRequest)
.Produces(StatusCodes.Status401Unauthorized)
.Produces(StatusCodes.Status423Locked);


app.MapGet("/api/history", async (
    ClaimsPrincipal userPrincipal,
    UserManager<User> userManager,
    ApplicationDbContext dbContext,
    ILogger<Program> logger
    ) => {
    logger.LogInformation("Executando /api/history...");
    var userId = userManager.GetUserId(userPrincipal);
    if (userId == null) return Results.Unauthorized();
    var history = await dbContext.GenerationHistory.Where(h => h.UserId == userId).OrderByDescending(h => h.Timestamp)
        .Select(h => new { h.Id, h.Timestamp, h.ContentType, h.InputPrompt, h.OutputText, OutputImagePreview = h.ContentType == "Image" && !string.IsNullOrEmpty(h.OutputImageBase64) ? "data:image/png;base64,..." : null, h.ModelUsed, h.Language })
        .ToListAsync();
    logger.LogInformation("Retornando {Count} registros de histórico para {UserId}", history.Count, userId);
    return Results.Ok(history);
})
.WithName("GetUserHistory").WithOpenApi().RequireAuthorization();

app.MapGet("/api/dashboard/summary", async (
    ClaimsPrincipal userPrincipal,
    UserManager<User> userManager,
    ApplicationDbContext dbContext,
    Backend.Services.IPlanService planService,
    ILogger<Program> logger
    ) => {
    logger.LogInformation("Executando /api/dashboard/summary...");
    var userId = userManager.GetUserId(userPrincipal);
    if (userId == null) return Results.Unauthorized();
    var user = await userManager.Users.FirstOrDefaultAsync(u => u.Id == userId);
    if (user == null) return Results.NotFound("Usuário não encontrado.");

    if (string.IsNullOrEmpty(user.CurrentPlanName) || user.SubscriptionCycleStart == default)
    {
        user.CurrentPlanName ??= "Free";
        if (user.SubscriptionCycleStart == default) { user.SubscriptionCycleStart = new DateTime(DateTime.UtcNow.Year, DateTime.UtcNow.Month, 1, 0, 0, 0, DateTimeKind.Utc); }
        logger.LogInformation("Atualizando plano/ciclo para usuário {UserId} no dashboard.", userId);
        await userManager.UpdateAsync(user);
    }

    var planDetails = planService.GetPlanDetails(user.CurrentPlanName) ?? planService.GetDefaultPlan();
    var cycleStartDate = user.SubscriptionCycleStart == DateTime.MinValue ? new DateTime(DateTime.UtcNow.Year, DateTime.UtcNow.Month, 1, 0, 0, 0, DateTimeKind.Utc) : user.SubscriptionCycleStart;
    var nextCycleStartDate = cycleStartDate.AddMonths(1);

    var textGenerationsThisCycle = await dbContext.GenerationHistory.CountAsync(h => h.UserId == userId && h.ContentType == "Text" && h.Timestamp >= cycleStartDate && h.Timestamp < nextCycleStartDate);
    var thumbnailGenerationsThisCycle = await dbContext.GenerationHistory.CountAsync(h => h.UserId == userId && h.ContentType == "Image" && h.Timestamp >= cycleStartDate && h.Timestamp < nextCycleStartDate);
    logger.LogInformation("Resumo para {UserId}: Plano={Plan}, Texto={UsedText}/{LimitText}, Thumb={UsedThumb}/{LimitThumb}", userId, planDetails.DisplayName, textGenerationsThisCycle, planDetails.TextGenerationsLimit, thumbnailGenerationsThisCycle, planDetails.ThumbnailGenerationsLimit);

    return Results.Ok(new {
        PlanName = planDetails.DisplayName,
        SubscriptionCycleStartDate = cycleStartDate,
        SubscriptionCycleEndDate = nextCycleStartDate.AddDays(-1),
        TextGenerationsUsed = textGenerationsThisCycle,
        TextGenerationsLimit = planDetails.TextGenerationsLimit,
        TextGenerationsRemaining = Math.Max(0, planDetails.TextGenerationsLimit - textGenerationsThisCycle),
        ThumbnailGenerationsUsed = thumbnailGenerationsThisCycle,
        ThumbnailGenerationsLimit = planDetails.ThumbnailGenerationsLimit,
        ThumbnailGenerationsRemaining = Math.Max(0, planDetails.ThumbnailGenerationsLimit - thumbnailGenerationsThisCycle)
    });
})
.WithName("GetDashboardSummary").WithOpenApi().RequireAuthorization();

app.MapGet("/api/account/details", async (
    ClaimsPrincipal userPrincipal,
    UserManager<User> userManager,
    Backend.Services.IPlanService planService,
    ILogger<Program> logger
    ) => {
    logger.LogInformation("Executando /api/account/details...");
    var userId = userManager.GetUserId(userPrincipal);
    if (userId == null) return Results.Unauthorized();
    var user = await userManager.Users.Include(u => u.GenerationHistory).FirstOrDefaultAsync(u => u.Id == userId); // Exemplo de Include se necessário
    if (user == null) return Results.NotFound(new { message = "Usuário não encontrado." });

    if (string.IsNullOrEmpty(user.CurrentPlanName) || user.SubscriptionCycleStart == default)
    {
        user.CurrentPlanName ??= "Free";
        if (user.SubscriptionCycleStart == default) { user.SubscriptionCycleStart = new DateTime(DateTime.UtcNow.Year, DateTime.UtcNow.Month, 1, 0, 0, 0, DateTimeKind.Utc); }
    }

    var planDetails = planService.GetPlanDetails(user.CurrentPlanName) ?? planService.GetDefaultPlan();
    var cycleStartDate = user.SubscriptionCycleStart == DateTime.MinValue ? new DateTime(DateTime.UtcNow.Year, DateTime.UtcNow.Month, 1, 0, 0, 0, DateTimeKind.Utc) : user.SubscriptionCycleStart;
    var nextCycleStartDate = cycleStartDate.AddMonths(1);

    string? stripeCustomerId = user.StripeCustomerId;
    string? stripeSubscriptionId = user.StripeSubscriptionId;
    logger.LogInformation("Retornando detalhes da conta para {UserId}", userId);

    return Results.Ok(new {
        user.Email,
        user.UserName,
        user.CreatedAt,
        CurrentPlanDisplayName = planDetails.DisplayName,
        CurrentPlanInternalName = user.CurrentPlanName,
        SubscriptionCycleStartDate = cycleStartDate,
        SubscriptionCycleEndDate = nextCycleStartDate.AddDays(-1),
        StripeCustomerId = stripeCustomerId,
        StripeSubscriptionId = stripeSubscriptionId
    });
})
.WithName("GetAccountDetails").WithOpenApi().RequireAuthorization();

app.MapGet("/api/plans", (
    Backend.Services.IPlanService planService,
    ILogger<Program> logger
    ) =>
{
    logger.LogInformation("Executando /api/plans...");
    var allPlans = planService.GetAllPlans();
    if (allPlans == null || !allPlans.Any())
    {
        logger.LogWarning("Nenhum plano encontrado pelo PlanService.");
        return Results.NotFound(new { message = "Nenhum plano encontrado." });
    }
    logger.LogInformation("Retornando {Count} planos.", allPlans.Count());
    return Results.Ok(allPlans);
})
.WithName("GetAvailablePlans").WithOpenApi();

app.MapPost("/api/stripe/create-checkout-session", async (
    [FromBody] CreateCheckoutSessionRequest request,
    ClaimsPrincipal userPrincipal,
    UserManager<User> userManager,
    IConfiguration configuration,
    HttpContext httpContext,
    ILogger<Program> logger
    ) =>
{
    logger.LogInformation("Executando /api/stripe/create-checkout-session...");
    var userId = userManager.GetUserId(userPrincipal);
    if (userId == null) return Results.Unauthorized();
    var user = await userManager.FindByIdAsync(userId);
    if (user == null) return Results.NotFound("Usuário não encontrado.");

    var frontendBaseUrl = configuration["FrontendBaseUrl"] ?? "http://localhost:3000";
    var successUrl = $"{frontendBaseUrl}/payment/success?session_id={{CHECKOUT_SESSION_ID}}";
    var cancelUrl = $"{frontendBaseUrl}/payment/cancel";

    logger.LogInformation("Criando sessão de checkout para Usuário {UserId} e PriceId {PriceId}", userId, request.PriceId);
    var options = new SessionCreateOptions
    {
        PaymentMethodTypes = new List<string> { "card" },
        LineItems = new List<SessionLineItemOptions> { new SessionLineItemOptions { Price = request.PriceId, Quantity = 1, }, },
        Mode = "subscription", SuccessUrl = successUrl, CancelUrl = cancelUrl, ClientReferenceId = userId,
        CustomerEmail = user.Email, // Pré-preencher email
    };

    try
    {
        var service = new SessionService();
        Session session = await service.CreateAsync(options);
        logger.LogInformation("Sessão de checkout {SessionId} criada para Usuário {UserId}", session.Id, userId);
        return Results.Ok(new { sessionId = session.Id });
    }
    catch (StripeException e)
    {
        logger.LogError(e, "[Stripe Checkout Error] Erro ao criar sessão para Usuário {UserId}: {ErrorMessage}", userId, e.StripeError?.Message ?? e.Message);
        return Results.Json(new { error = new { message = e.StripeError?.Message ?? e.Message } }, statusCode: StatusCodes.Status400BadRequest);
    }
    catch (Exception e)
    {
        logger.LogError(e, "[Stripe Checkout Error] Erro inesperado para Usuário {UserId}", userId);
        return Results.Problem(detail: "Ocorreu um erro inesperado ao processar seu pagamento.", statusCode: StatusCodes.Status500InternalServerError, title: "Erro Interno");
    }
})
.WithName("CreateStripeCheckoutSession").WithOpenApi().RequireAuthorization();

app.MapPost("/api/stripe/webhook", async (
    HttpRequest request,
    IConfiguration configuration,
    IServiceProvider serviceProvider,
    ILogger<Program> logger
    ) =>
{
    logger.LogInformation("Recebida requisição no endpoint /api/stripe/webhook");
    var json = await new StreamReader(request.Body).ReadToEndAsync();
    var webhookSecret = configuration["Stripe:WebhookSecret"];

    if (string.IsNullOrEmpty(webhookSecret))
    {
        logger.LogError("Segredo do Webhook do Stripe (Stripe:WebhookSecret) não configurado.");
        return Results.BadRequest("Webhook secret não configurado.");
    }

    try
    {
        var stripeEvent = EventUtility.ConstructEvent(json, request.Headers["Stripe-Signature"], webhookSecret);
        logger.LogInformation("[Webhook] Evento verificado e recebido: {EventType} ({EventId})", stripeEvent.Type, stripeEvent.Id);

        await using var scope = serviceProvider.CreateAsyncScope();
        var userManager = scope.ServiceProvider.GetRequiredService<UserManager<User>>();
        var dbContext = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        var planService = scope.ServiceProvider.GetRequiredService<Backend.Services.IPlanService>();

        switch (stripeEvent.Type)
        {
            case Events.CheckoutSessionCompleted:
                var session = stripeEvent.Data.Object as Session;
                if (session?.Mode == "subscription" && session.PaymentStatus == "paid")
                {
                    logger.LogInformation("[Webhook] Checkout Session Completed para ClientReferenceId: {ClientRefId}, SubscriptionId: {SubId}", session.ClientReferenceId, session.SubscriptionId);
                    var userId = session.ClientReferenceId;
                    var stripeSubscriptionId = session.SubscriptionId;
                    var stripeCustomerId = session.CustomerId;

                    if (string.IsNullOrEmpty(userId) || string.IsNullOrEmpty(stripeSubscriptionId) || string.IsNullOrEmpty(stripeCustomerId)) { logger.LogError("[Webhook] Dados essenciais faltando na sessão {SessionId}", session.Id); break; }
                    var user = await userManager.FindByIdAsync(userId);
                    if (user == null) { logger.LogError("[Webhook] Usuário não encontrado {UserId}", userId); break; }

                    var subscriptionService = new SubscriptionService();
                    var subscription = await subscriptionService.GetAsync(stripeSubscriptionId);
                    if (subscription == null || subscription.Items == null || !subscription.Items.Data.Any()) { logger.LogError("[Webhook] Assinatura não encontrada {SubId}", stripeSubscriptionId); break; }
                    var priceId = subscription.Items.Data[0].Price?.Id;
                    if (string.IsNullOrEmpty(priceId)) { logger.LogError("[Webhook] PriceId não encontrado na assinatura {SubId}", stripeSubscriptionId); break; }

                    string? newPlanName = null;
                    var stripePriceIdConfig = configuration.GetSection("Stripe:PriceIds").GetChildren().ToDictionary(x => x.Key, x => x.Value);
                    foreach(var kvp in stripePriceIdConfig) { if (kvp.Value == priceId) { if (kvp.Key.Contains("Essencial")) newPlanName = "Paid1"; else if (kvp.Key.Contains("Pro")) newPlanName = "Paid2"; break; } }

                    if (string.IsNullOrEmpty(newPlanName)) { logger.LogError("[Webhook] Mapeamento PriceId {PriceId} falhou.", priceId); break; }

                    user.CurrentPlanName = newPlanName;
                    user.StripeCustomerId = stripeCustomerId;
                    user.StripeSubscriptionId = stripeSubscriptionId;
                    user.SubscriptionCycleStart = subscription.CurrentPeriodStart.ToUniversalTime(); // Usar data UTC

                    var updateResult = await userManager.UpdateAsync(user);
                    if (updateResult.Succeeded) { logger.LogInformation("[Webhook] Usuário {UserId} atualizado para plano {PlanName} (Stripe Sub: {SubId})", userId, newPlanName, stripeSubscriptionId); }
                    else { logger.LogError("[Webhook] Falha ao atualizar usuário {UserId} com sub {SubId}: {Errors}", userId, stripeSubscriptionId, string.Join(", ", updateResult.Errors.Select(e => e.Description))); }
                } else { logger.LogInformation("[Webhook] Sessão checkout {SessionId} completada mas não relevante (Modo: {Mode}, Status Pag.: {PaymentStatus})", session?.Id, session?.Mode, session?.PaymentStatus); }
                break;

            case Events.CustomerSubscriptionUpdated:
                 var updatedSubscription = stripeEvent.Data.Object as Subscription;
                 logger.LogInformation("[Webhook] Evento CustomerSubscriptionUpdated recebido para SubId: {SubId}, Status: {Status}, CancelAtPeriodEnd: {CancelEnd}", updatedSubscription?.Id, updatedSubscription?.Status, updatedSubscription?.CancelAtPeriodEnd);
                 // TODO: Lógica para atualizar plano/status se necessário
                 break;
            case Events.CustomerSubscriptionDeleted:
                 var deletedSubscription = stripeEvent.Data.Object as Subscription;
                 logger.LogInformation("[Webhook] Evento CustomerSubscriptionDeleted recebido para SubId: {SubId}", deletedSubscription?.Id);
                 // TODO: Lógica para reverter plano do usuário
                 break;
            // TODO: Adicionar InvoicePaymentSucceeded/Failed se necessário
            default:
                logger.LogInformation("[Webhook] Evento não tratado: {EventType}", stripeEvent.Type);
                break;
        }
        return Results.Ok();
    }
    catch (StripeException e) { logger.LogError(e, "[Webhook] Erro Stripe: {ErrorMessage}", e.Message); return Results.BadRequest("Erro ao processar evento Stripe."); }
    catch (Exception e) { logger.LogError(e, "[Webhook] Erro inesperado."); return Results.StatusCode(StatusCodes.Status500InternalServerError, "Erro interno."); }
})
.WithName("StripeWebhook");


app.Run();
