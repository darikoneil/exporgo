//! The `exporgo` command-line interface. All interactivity (flags, prompts,
//! printing) lives here so the library stays UI-free.
use std::{io::IsTerminal, path::PathBuf, process::ExitCode};

use clap::{Parser, Subcommand, ValueEnum};

use crate::{
    check::check,
    plan::{ChangeKind, PlannedChange},
    stamp::{NewOptions, stamp},
    tokens::{Token, TokenValues},
    update::{UpdateOptions, update},
};

#[derive(Parser)]
#[command(version, about = "Stamp and maintain science-project workspaces")]
struct Cli
{
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command
{
    /// Create a new project from the embedded template
    New
    {
        /// Human project name; the folder name is its slug
        name: String,
        /// Parent directory to create the project in
        #[arg(long, default_value = ".")]
        path: PathBuf,
        /// One-line aim of the project
        #[arg(long)]
        aim: Option<String>,
        /// Project status
        #[arg(long, value_enum)]
        status: Option<Status>,
        /// Primary GitHub repository URL
        #[arg(long)]
        repo: Option<String>,
        /// Data root (e.g. a UNC path on the lab share)
        #[arg(long)]
        data_root: Option<String>,
        /// Project owner
        #[arg(long)]
        owner: Option<String>,
        /// Owner email
        #[arg(long)]
        email: Option<String>,
        /// Never prompt; unset values stay as {{TOKENS}} in context.md
        #[arg(long)]
        no_input: bool,
        /// Run `git init` in the new project (never commits)
        #[arg(long)]
        git: bool,
        /// Stamp into a non-empty directory, overwriting colliding files
        #[arg(long)]
        force: bool,
    },
    /// Report a project's drift from this binary's template
    Check
    {
        /// Project root (default: current directory)
        path: Option<PathBuf>,
    },
    /// Refresh a project's exporgo-owned files from this binary's template
    Update
    {
        /// Project root (default: current directory)
        path: Option<PathBuf>,
        /// Show what would change without writing anything
        #[arg(long)]
        dry_run: bool,
        /// Only refresh .claude/skills/exporgo/ (leaves the manifest version
        /// alone)
        #[arg(long)]
        skills_only: bool,
    },
    /// Two-hop, non-destructive folder sync (source <-> intermediate <->
    /// destination)
    Sync
    {
        /// Project root whose exporgo.toml [sync] section supplies defaults
        /// (default: current directory)
        path: Option<PathBuf>,
        /// Sync source folder (overrides the manifest)
        #[arg(long)]
        source: Option<PathBuf>,
        /// Durable local intermediate folder (overrides the manifest)
        #[arg(long)]
        intermediate: Option<PathBuf>,
        /// Sync destination folder (overrides the manifest)
        #[arg(long)]
        destination: Option<PathBuf>,
        /// Forward: source -> intermediate -> destination; reverse runs the
        /// other way
        #[arg(long, value_enum, default_value_t = DirectionArg::Forward)]
        direction: DirectionArg,
        /// Extra file-name patterns to exclude (repeatable; * wildcards)
        #[arg(long)]
        exclude: Vec<String>,
        /// Also DELETE target entries absent from the source (destructive)
        #[arg(long)]
        mirror: bool,
        /// Log what would happen; copy and delete nothing
        #[arg(long)]
        dry_run: bool,
        /// Where the sync logs are written (default: the project root)
        #[arg(long)]
        log_dir: Option<PathBuf>,
    },
    /// Manage documented experiments inside a project
    Experiment
    {
        #[command(subcommand)]
        command: ExperimentCommand,
    },
}

#[derive(Subcommand)]
enum ExperimentCommand
{
    /// Stamp experiments/_TEMPLATE/ into experiments/<slug>/ and fill its
    /// tokens
    New
    {
        /// Human experiment name; the folder name is its slug
        name: String,
        /// Project root (default: current directory)
        #[arg(long, default_value = ".")]
        path: PathBuf,
        /// Raw data root (default: derived as <project data_root>/<slug>)
        #[arg(long)]
        data_root: Option<String>,
        /// Processed data root (never derived — labs lay these out differently)
        #[arg(long)]
        processed_root: Option<String>,
        /// Never prompt; unset values stay as {{TOKENS}} in the stamped files
        #[arg(long)]
        no_input: bool,
    },
}

#[derive(Clone, Copy, ValueEnum)]
enum DirectionArg
{
    Forward,
    Reverse,
}

#[derive(Clone, Copy, ValueEnum)]
enum Status
{
    Planning,
    Active,
    Analysis,
    Writing,
    Archived,
}

impl Status
{
    const ALL: [Status; 5] = [
        Status::Planning,
        Status::Active,
        Status::Analysis,
        Status::Writing,
        Status::Archived,
    ];

    fn as_str(self) -> &'static str
    {
        match self
        {
            Status::Planning => "planning",
            Status::Active => "active",
            Status::Analysis => "analysis",
            Status::Writing => "writing",
            Status::Archived => "archived",
        }
    }
}

/// Parses arguments, runs the command, prints the outcome, returns the exit
/// code.
pub fn run() -> ExitCode
{
    let cli = Cli::parse();
    let result = match cli.command
    {
        Command::New {
            name,
            path,
            aim,
            status,
            repo,
            data_root,
            owner,
            email,
            no_input,
            git,
            force,
        } => run_new(NewArgs {
            name,
            path,
            aim,
            status,
            repo,
            data_root,
            owner,
            email,
            no_input,
            git,
            force,
        }),
        Command::Check { path } => run_check(path.unwrap_or_else(|| PathBuf::from("."))),
        Command::Update {
            path,
            dry_run,
            skills_only,
        } => run_update(
            path.unwrap_or_else(|| PathBuf::from(".")),
            UpdateOptions {
                dry_run,
                skills_only,
            },
        ),
        Command::Sync {
            path,
            source,
            intermediate,
            destination,
            direction,
            exclude,
            mirror,
            dry_run,
            log_dir,
        } => run_sync(SyncArgs {
            path: path.unwrap_or_else(|| PathBuf::from(".")),
            source,
            intermediate,
            destination,
            direction,
            exclude,
            mirror,
            dry_run,
            log_dir,
        }),
        Command::Experiment {
            command:
                ExperimentCommand::New {
                    name,
                    path,
                    data_root,
                    processed_root,
                    no_input,
                },
        } => run_experiment_new(name, path, data_root, processed_root, no_input),
    };
    match result
    {
        Ok(code) => code,
        Err(e) =>
        {
            eprintln!("error: {e}");
            // Exit 2 for genuine errors, so scripts can tell "check found
            // drift" (exit 1) from "the command itself failed".
            ExitCode::from(2)
        }
    }
}

struct NewArgs
{
    name: String,
    path: PathBuf,
    aim: Option<String>,
    status: Option<Status>,
    repo: Option<String>,
    data_root: Option<String>,
    owner: Option<String>,
    email: Option<String>,
    no_input: bool,
    git: bool,
    force: bool,
}

fn run_new(args: NewArgs) -> Result<ExitCode, crate::Error>
{
    let values = resolve_tokens(&args);
    let report = stamp(&NewOptions {
        name: args.name,
        parent: args.path,
        values,
        force: args.force,
        git_init: args.git,
    })?;
    println!(
        "Created {} ({} files, {} directories)",
        report.root.display(),
        report.files_written,
        report.dirs_created
    );
    if !report.unfilled.is_empty()
    {
        println!(
            "Unfilled tokens in context.md (fill by hand or leave for later): {}",
            report.unfilled.join(", ")
        );
    }
    if let Some(warning) = report.git_warning
    {
        eprintln!("warning: {warning}");
    }
    Ok(ExitCode::SUCCESS)
}

/// Flags first; anything missing is prompted for unless prompting is disabled
/// (`--no-input`, or stdin is not a terminal). Empty answers skip the token.
fn resolve_tokens(args: &NewArgs) -> TokenValues
{
    let mut values = TokenValues::new();
    let from_flags = [
        (Token::OneLineAim, &args.aim),
        (Token::RepoUrl, &args.repo),
        (Token::DataRoot, &args.data_root),
        (Token::Owner, &args.owner),
        (Token::OwnerEmail, &args.email),
    ];
    for (token, value) in from_flags
    {
        if let Some(value) = value
        {
            values.insert(token, value.clone());
        }
    }
    if let Some(status) = args.status
    {
        values.insert(Token::Status, status.as_str().to_string());
    }

    let interactive = !args.no_input && std::io::stdin().is_terminal();
    if !interactive
    {
        return values;
    }

    prompt_text(&mut values, Token::OneLineAim, "One-line aim");
    prompt_status(&mut values);
    prompt_text(&mut values, Token::RepoUrl, "Primary repo URL");
    prompt_text(&mut values, Token::DataRoot, "Data root");
    prompt_text(&mut values, Token::Owner, "Owner");
    prompt_text(&mut values, Token::OwnerEmail, "Owner email");
    values
}

fn prompt_text(values: &mut TokenValues, token: Token, label: &str)
{
    if values.contains_key(&token)
    {
        return;
    }
    let answer: Result<String, _> = dialoguer::Input::new()
        .with_prompt(format!("{label} (Enter to skip)"))
        .allow_empty(true)
        .interact_text();
    if let Ok(answer) = answer
    {
        let answer = answer.trim().to_string();
        if !answer.is_empty()
        {
            values.insert(token, answer);
        }
    }
}

fn prompt_status(values: &mut TokenValues)
{
    if values.contains_key(&Token::Status)
    {
        return;
    }
    let mut items: Vec<&str> = Status::ALL.iter().map(|s| s.as_str()).collect();
    items.push("(skip)");
    if let Ok(index) = dialoguer::Select::new()
        .with_prompt("Status")
        .items(&items)
        .default(0)
        .interact()
        && index < Status::ALL.len()
    {
        values.insert(Token::Status, Status::ALL[index].as_str().to_string());
    }
}

struct SyncArgs
{
    path: PathBuf,
    source: Option<PathBuf>,
    intermediate: Option<PathBuf>,
    destination: Option<PathBuf>,
    direction: DirectionArg,
    exclude: Vec<String>,
    mirror: bool,
    dry_run: bool,
    log_dir: Option<PathBuf>,
}

/// Merges flags over the manifest's optional `[sync]` section; flags win per
/// field.
fn run_sync(args: SyncArgs) -> Result<ExitCode, crate::Error>
{
    use crate::{
        manifest::Manifest,
        sync::{Direction, SyncOptions, sync},
    };

    // Only "not a project" falls through to flags-only mode: a manifest that
    // exists but is malformed (e.g. a [sync] table missing a field) must
    // surface its real parse error, not a misleading "no [sync] section".
    let manifest = match Manifest::load(&args.path)
    {
        Ok(manifest) => Some(manifest),
        Err(crate::Error::NotAProject(_)) => None,
        Err(e) => return Err(e),
    };
    let config = manifest.as_ref().and_then(|m| m.sync.as_ref());

    let resolve = |flag: Option<PathBuf>, configured: Option<&String>| {
        flag.or_else(|| configured.map(PathBuf::from))
    };
    let source = resolve(args.source, config.map(|c| &c.source));
    let intermediate = resolve(args.intermediate, config.map(|c| &c.intermediate));
    let destination = resolve(args.destination, config.map(|c| &c.destination));

    let missing: Vec<&str> = [
        ("source", source.is_none()),
        ("intermediate", intermediate.is_none()),
        ("destination", destination.is_none()),
    ]
    .iter()
    .filter(|(_, absent)| *absent)
    .map(|(name, _)| *name)
    .collect();
    if !missing.is_empty()
    {
        return Err(crate::Error::SyncUnconfigured(missing.join(", ")));
    }

    let mut exclude = config.map(|c| c.exclude.clone()).unwrap_or_default();
    exclude.extend(args.exclude);

    let options = SyncOptions {
        source: source.expect("checked above"),
        intermediate: intermediate.expect("checked above"),
        destination: destination.expect("checked above"),
        direction: match args.direction
        {
            DirectionArg::Forward => Direction::Forward,
            DirectionArg::Reverse => Direction::Reverse,
        },
        exclude,
        mirror: args.mirror,
        dry_run: args.dry_run,
        log_dir: args.log_dir.unwrap_or_else(|| args.path.clone()),
    };

    if options.mirror && !options.dry_run
    {
        eprintln!("warning: --mirror DELETES files at the target that are absent from the source");
    }

    let report = sync(&options)?;
    println!("{}", report.summary);
    if matches!(options.direction, Direction::Reverse)
    {
        println!("Reverse done: a cloud-drive client will now upload the source-side changes.");
    }
    println!("History: {}", report.history_log.display());
    println!("Detail:  {}", report.detail_log.display());
    Ok(ExitCode::SUCCESS)
}

fn run_experiment_new(
    name: String,
    path: PathBuf,
    data_root: Option<String>,
    processed_root: Option<String>,
    no_input: bool,
) -> Result<ExitCode, crate::Error>
{
    use crate::experiment::{NewExperimentOptions, stamp_experiment};

    // The raw root is derivable from the manifest, so only the processed root
    // (which is never derived) is worth a prompt.
    let mut processed_root = processed_root;
    let interactive = !no_input && std::io::stdin().is_terminal();
    if processed_root.is_none() && interactive
    {
        let answer: Result<String, _> = dialoguer::Input::new()
            .with_prompt("Processed data root (Enter to skip)")
            .allow_empty(true)
            .interact_text();
        if let Ok(answer) = answer
        {
            let answer = answer.trim().to_string();
            if !answer.is_empty()
            {
                processed_root = Some(answer);
            }
        }
    }

    let report = stamp_experiment(&NewExperimentOptions {
        project_root: path,
        name,
        raw_data_root: data_root,
        processed_data_root: processed_root,
    })?;
    println!(
        "Created {} ({} files)",
        report.dir.display(),
        report.files_written
    );
    if !report.unfilled.is_empty()
    {
        println!(
            "Unfilled tokens (fill by hand or leave for later): {}",
            report.unfilled.join(", ")
        );
    }
    Ok(ExitCode::SUCCESS)
}

fn run_check(path: PathBuf) -> Result<ExitCode, crate::Error>
{
    let report = check(&path)?;
    if report.project_version == report.binary_version
    {
        println!("Template version: {} (current)", report.project_version);
    }
    else if report.project_version > report.binary_version
    {
        println!(
            "Template version: project {} is NEWER than this binary {} — download a newer release",
            report.project_version, report.binary_version
        );
    }
    else
    {
        println!(
            "Template version: project {} → binary {}",
            report.project_version, report.binary_version
        );
    }
    print_changes("Update would apply", &report.changes);
    if !report.unfilled_tokens.is_empty()
    {
        println!(
            "Unfilled tokens in context.md: {}",
            report.unfilled_tokens.join(", ")
        );
    }
    if !report.missing_dirs.is_empty()
    {
        println!(
            "Missing standard directories: {}",
            report.missing_dirs.join(", ")
        );
    }
    if report.is_clean()
    {
        println!("Project is up to date.");
        Ok(ExitCode::SUCCESS)
    }
    else
    {
        Ok(ExitCode::FAILURE)
    }
}

fn run_update(path: PathBuf, options: UpdateOptions) -> Result<ExitCode, crate::Error>
{
    let dry_run = options.dry_run;
    let changes = update(&path, &options)?;
    if dry_run
    {
        print_changes("Would apply", &changes);
    }
    else if changes.is_empty()
    {
        println!("Already up to date.");
    }
    else
    {
        print_changes("Applied", &changes);
    }
    Ok(ExitCode::SUCCESS)
}

fn print_changes(heading: &str, changes: &[PlannedChange])
{
    if changes.is_empty()
    {
        return;
    }
    println!("{heading} ({} files):", changes.len());
    for change in changes
    {
        let kind = match change.kind
        {
            ChangeKind::Create => "create",
            ChangeKind::Overwrite => "overwrite",
        };
        println!("  {kind:9} {}", change.rel);
    }
}

#[cfg(test)]
mod tests
{
    use pretty_assertions::assert_eq;

    use super::*;

    fn new_args() -> NewArgs
    {
        NewArgs {
            name: "Pilot".to_string(),
            path: PathBuf::from("."),
            aim: Some("Does it remap?".to_string()),
            status: Some(Status::Analysis),
            repo: Some("https://github.com/org/repo".to_string()),
            data_root: Some(r"\ktdata\snlkt\data".to_string()),
            owner: Some("Darik".to_string()),
            email: Some("doneil@salk.edu".to_string()),
            no_input: true, // never prompt in tests
            git: false,
            force: false,
        }
    }

    #[test]
    fn resolve_tokens_maps_every_flag_to_its_token()
    {
        let values = resolve_tokens(&new_args());
        let expected: [(Token, &str); 6] = [
            (Token::OneLineAim, "Does it remap?"),
            (Token::Status, "analysis"),
            (Token::RepoUrl, "https://github.com/org/repo"),
            (Token::DataRoot, r"\ktdata\snlkt\data"),
            (Token::Owner, "Darik"),
            (Token::OwnerEmail, "doneil@salk.edu"),
        ];
        for (token, value) in expected
        {
            assert_eq!(values.get(&token).map(String::as_str), Some(value));
        }
        // Name and created date are stamp's job, never the flag resolver's.
        assert!(!values.contains_key(&Token::ProjectName));
        assert!(!values.contains_key(&Token::CreatedDate));
    }

    #[test]
    fn absent_flags_leave_tokens_unset()
    {
        let mut args = new_args();
        args.aim = None;
        args.status = None;
        let values = resolve_tokens(&args);
        assert!(!values.contains_key(&Token::OneLineAim));
        assert!(!values.contains_key(&Token::Status));
        assert_eq!(values.len(), 4);
    }

    /// The status vocabulary is a contract with the template's context.md
    /// ("planning | active | analysis | writing | archived").
    #[test]
    fn status_strings_match_the_template_vocabulary()
    {
        let rendered: Vec<&str> = Status::ALL.iter().map(|s| s.as_str()).collect();
        assert_eq!(
            rendered,
            vec!["planning", "active", "analysis", "writing", "archived"]
        );
    }
}
